bl_info = {
    "name": "Jellyfish AI",
    "author": "Pool Andres Aguilar Apolinario (Akimsa3)",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Jellyfish AI",
    "description": "CCM somatic-engine-driven sea creatures (jellyfish/turtle/fish): "
                   "perceive each other and objects, react (flee/feed/idle) and "
                   "bake their own animation.",
    "category": "Animation",
}

import json
import math
import os
import random

import bpy
from mathutils import Vector

from .jelly_core import JellyfishEngine, TICK_SECONDS

SPECIES_KEY = "jelly_species"  # custom property marking an object as an engine-driven creature

# -- per-species rig geometry ------------------------------------------------
# Every species has one "body" bone (translation/orientation reference) plus
# a small set of secondary bones. Coordinates are local edit-bone head/tail.
N_TENTACLES = 6
TENTACLE_LEN = 0.6

SPECIES_RIGS = {
    "jellyfish": {
        "body": ((0, 0, 0), (0, 0, 0.5)),
        "bones": None,  # built specially below (radial tentacles)
    },
    "turtle": {
        "body": ((0, 0, 0), (0.5, 0, 0)),
        "bones": [
            ("neck",  (0.5, 0, 0),      (0.75, 0, 0.12), "body"),
            ("head",  (0.75, 0, 0.12),  (0.95, 0, 0.12), "neck"),
            ("fin_1", (0.15, 0.3, 0),   (-0.05, 0.55, 0), "body"),   # front right
            ("fin_2", (0.15, -0.3, 0),  (-0.05, -0.55, 0), "body"),  # front left
            ("fin_3", (-0.2, 0.25, 0),  (-0.45, 0.4, 0), "body"),    # back right
            ("fin_4", (-0.2, -0.25, 0), (-0.45, -0.4, 0), "body"),   # back left
        ],
    },
    "fish": {
        "body": ((0, 0, 0), (0.3, 0, 0)),
        "bones": [
            ("head",  (0.3, 0, 0), (0.5, 0, 0), "body"),
            ("tail",  (0, 0, 0),   (-0.35, 0, 0), "body"),
            ("fin_1", (0.05, 0.12, 0),  (-0.05, 0.3, 0),  "body"),   # right pectoral fin
            ("fin_2", (0.05, -0.12, 0), (-0.05, -0.3, 0), "body"),   # left pectoral fin
        ],
    },
}

# which bones react to contraction (pulse, jellyfish-only) vs. a swim
# stroke (paddle/tail-beat, driven by speed for turtle/fish, by chem
# "wave" for jellyfish)
SPECIES_MOTION = {
    "jellyfish": {"pulse_bone": "body", "wave_bones": [f"tentacle_{i}_1" for i in range(N_TENTACLES)], "wave_axis": 0},
    "turtle":    {"pulse_bone": None,   "wave_bones": ["fin_1", "fin_2", "fin_3", "fin_4"], "wave_axis": 2},
    "fish":      {"pulse_bone": None,   "wave_bones": ["tail", "fin_1", "fin_2"], "wave_axis": 2},
}

# Illustrative per-species top speed, editable per instance afterwards
# (see create_species_rig). Detection stays global/omnidirectional (sense
# via smell/pressure/sound, not a vision cone -- see scene sense radius).
SPECIES_SENSE_DEFAULTS = {
    "jellyfish": {"max_speed": 1.5},
    "turtle":    {"max_speed": 1.2},
    "fish":      {"max_speed": 3.0},
}

DANGER_KEYWORDS = ("danger", "predator", "shark", "turtle", "threat")
FOOD_KEYWORDS = ("food", "fish", "prey", "shrimp", "plankton")


# -- perception ---------------------------------------------------------
# Classify by user-set custom property first (jelly_damage / jelly_food_value
# -- see Mark as Predator/Food), then by name keyword (this already makes
# "Turtle AI" read as danger and "Fish AI" as food to everyone else, since
# the rig's own name matches the same keyword lists), then by relative size.

def classify_object(obj, viewer_obj):
    if SPECIES_KEY in obj.keys() and SPECIES_KEY in viewer_obj.keys() and obj[SPECIES_KEY] == viewer_obj[SPECIES_KEY]:
        return None  # same-species creatures are conspecifics, handled separately (sense_conspecific)
    if "jelly_damage" in obj.keys():
        return "danger"
    if "jelly_food_value" in obj.keys():
        return "food"
    name = obj.name.lower()
    if any(k in name for k in DANGER_KEYWORDS):
        return "danger"
    if any(k in name for k in FOOD_KEYWORDS):
        return "food"
    v_size = max(viewer_obj.dimensions.x, viewer_obj.dimensions.y, viewer_obj.dimensions.z, 0.01)
    o_size = max(obj.dimensions.x, obj.dimensions.y, obj.dimensions.z, 0.01)
    ratio = o_size / v_size
    if ratio > 1.3:
        return "danger"
    if ratio < 0.8:
        return "food"
    return "unclassifiable"  # sensed but not clearly food or danger by name/size


def nearest_relevant_object(scene, viewer_obj, sense_radius):
    v_pos = viewer_obj.matrix_world.translation
    best = None
    best_dist = sense_radius
    for obj in scene.objects:
        if obj == viewer_obj:
            continue
        category = classify_object(obj, viewer_obj)
        if category is None:
            continue
        dist = (obj.matrix_world.translation - v_pos).length
        if dist <= best_dist:
            best = (obj, category, dist)
            best_dist = dist
    return best  # (obj, category, dist) or None


def nearest_conspecific(scene, viewer_obj, sense_radius):
    if SPECIES_KEY not in viewer_obj.keys():
        return None
    species = viewer_obj[SPECIES_KEY]
    v_pos = viewer_obj.matrix_world.translation
    best, best_dist = None, sense_radius
    for obj in scene.objects:
        if obj == viewer_obj or obj.get(SPECIES_KEY) != species:
            continue
        dist = (obj.matrix_world.translation - v_pos).length
        if dist <= best_dist:
            best, best_dist = obj, dist
    return (best, best_dist) if best else None


# -- rig creation ---------------------------------------------------------

def create_species_rig(context, species, name):
    if name in bpy.data.objects:
        return bpy.data.objects[name]

    spec = SPECIES_RIGS[species]
    arm_data = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm_data)
    context.collection.objects.link(rig)
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    body = eb.new("body")
    body.head, body.tail = spec["body"]

    if species == "jellyfish":
        for i in range(N_TENTACLES):
            angle = (2 * math.pi / N_TENTACLES) * i
            x = 0.15 * math.cos(angle)
            y = 0.15 * math.sin(angle)
            seg1 = eb.new(f"tentacle_{i}_1")
            seg1.head = (x, y, 0)
            seg1.tail = (x, y, -TENTACLE_LEN * 0.5)
            seg1.parent = body
            seg1.use_connect = False
            seg2 = eb.new(f"tentacle_{i}_2")
            seg2.head = seg1.tail
            seg2.tail = (x, y, -TENTACLE_LEN)
            seg2.parent = seg1
            seg2.use_connect = True
    else:
        for bname, head, tail, parent in spec["bones"]:
            b = eb.new(bname)
            b.head = head
            b.tail = tail
            b.parent = eb.get(parent)
            b.use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")
    rig[SPECIES_KEY] = species
    rig.rotation_mode = 'QUATERNION'

    defaults = SPECIES_SENSE_DEFAULTS[species]
    rig["jelly_max_speed"] = defaults["max_speed"]
    rig.id_properties_ui("jelly_max_speed").update(
        min=0.0, max=10.0, soft_min=0.0, soft_max=10.0,
        description="This creature's own top speed (units/second at motion speed=1.0)")

    return rig


def apply_species_motion(creature_obj, species, motion, frame):
    spec = SPECIES_MOTION[species]
    if spec["pulse_bone"]:
        b = creature_obj.pose.bones.get(spec["pulse_bone"])
        if b:
            c = motion["contraction"]
            b.scale = (1.0 + c * 0.15, 1.0 + c * 0.15, 1.0 - c * 0.3)
            b.keyframe_insert(data_path="scale", frame=frame)

    stroke = 0.3 + motion["speed"] * 0.7
    freq = 0.2 + motion["speed"] * 0.8
    axis = spec["wave_axis"]
    for idx, bname in enumerate(spec["wave_bones"]):
        b = creature_obj.pose.bones.get(bname)
        if not b:
            continue
        # turtle/fish: bilateral pairs alternate phase (opposite-side fins
        # flap out of sync, like real paddling/rowing); jellyfish tentacles
        # ripple around the bell instead, so they keep their own idx*0.3 stagger
        phase = (math.pi if (species != "jellyfish" and idx % 2 == 1) else 0) + idx * 0.3
        amplitude = stroke * motion["wave"] if species == "jellyfish" else stroke
        val = amplitude * math.sin(frame * freq * 0.3 + phase)
        b.rotation_mode = 'XYZ'
        rot = [0.0, 0.0, 0.0]
        rot[axis] = val
        b.rotation_euler = rot
        b.keyframe_insert(data_path="rotation_euler", frame=frame)


# -- operators --------------------------------------------------------------

class JELLY_OT_create_rig(bpy.types.Operator):
    bl_idname = "jellyfish_ai.create_rig"
    bl_label = "Create Creature Rig"
    bl_description = "Generates a species rig (jellyfish/turtle/fish) driven by its own CCM engine"

    def execute(self, context):
        scene = context.scene
        species = scene.jellyfish_ai_species
        name = scene.jellyfish_ai_new_name or f"{species.capitalize()} AI"
        create_species_rig(context, species, name)
        self.report({'INFO'}, f"'{name}' ({species}) rig created")
        return {'FINISHED'}


class JELLY_OT_mark_predator(bpy.types.Operator):
    bl_idname = "jellyfish_ai.mark_predator"
    bl_label = "Mark Selected as Predator"
    bl_description = ("Adds an editable 'jelly_damage' slider to each selected "
                       "object -- how much health it drains per contact tick "
                       "from any creature that touches it. Overrides name/size.")

    def execute(self, context):
        for obj in context.selected_objects:
            obj["jelly_damage"] = obj.get("jelly_damage", 2.0)
            obj.id_properties_ui("jelly_damage").update(
                min=0.0, max=10.0, soft_min=0.0, soft_max=10.0,
                description="Health drained per contact tick from a creature that touches this")
        self.report({'INFO'}, "Marked as predator (see Object Properties > Custom Properties)")
        return {'FINISHED'}


class JELLY_OT_mark_food(bpy.types.Operator):
    bl_idname = "jellyfish_ai.mark_food"
    bl_label = "Mark Selected as Food"
    bl_description = ("Adds an editable 'jelly_food_value' slider to each "
                       "selected object -- how much hunger/energy it "
                       "restores when eaten. Overrides name/size.")

    def execute(self, context):
        for obj in context.selected_objects:
            obj["jelly_food_value"] = obj.get("jelly_food_value", 1.0)
            obj.id_properties_ui("jelly_food_value").update(
                min=0.0, max=5.0, soft_min=0.0, soft_max=5.0,
                description="Multiplies the hunger/energy gained when eaten")
        self.report({'INFO'}, "Marked as food (see Object Properties > Custom Properties)")
        return {'FINISHED'}


class JELLY_OT_bake(bpy.types.Operator):
    bl_idname = "jellyfish_ai.bake"
    bl_label = "Bake All Creatures"
    bl_description = ("Runs every creature's own CCM engine across the scene's "
                       "frame range, IN LOCKSTEP so they react to each other, "
                       "and keyframes each one's reaction. A story JSON records "
                       "one combined event per bake, resuming every creature's "
                       "engine state from the previous event if present.")

    def execute(self, context):
        scene = context.scene
        creature_objs = [o for o in scene.objects if SPECIES_KEY in o.keys()]
        if not creature_objs:
            self.report({'ERROR'}, "No creature rigs found -- create at least one first")
            return {'CANCELLED'}

        fps = scene.render.fps / scene.render.fps_base
        ticks_per_frame_gap = max(1, round(TICK_SECONDS * fps))
        sense_radius = scene.jellyfish_ai_sense_radius
        contact_radius = scene.jellyfish_ai_contact_radius
        default_max_speed = scene.jellyfish_ai_max_speed
        default_damage = scene.jellyfish_ai_default_damage

        json_path = bpy.path.abspath(scene.jellyfish_ai_json_path)
        story = {"events": []}
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    story = json.load(f)
            except (json.JSONDecodeError, OSError):
                story = {"events": []}

        prev_creatures = story["events"][-1]["creatures"] if story["events"] else {}

        engines = {}
        heading_dirs = {}
        logs = {}
        stimuli_seen = {}
        last_health = {}  # for conspecific "injured protects healthy" logic
        eaten_records = {}  # creature name -> its final record, for creatures eaten mid-bake
        for obj in creature_objs:
            eng = JellyfishEngine()
            if obj.name in prev_creatures:
                eng.set_state(prev_creatures[obj.name]["engine_state_end"])
            engines[obj.name] = eng
            heading_dirs[obj.name] = Vector((1, 0, 0))
            logs[obj.name] = []
            stimuli_seen[obj.name] = {}
            last_health[obj.name] = 10.0

        frame = scene.frame_start
        while frame <= scene.frame_end:
            scene.frame_set(frame)
            context.view_layer.update()

            # re-fetch alive creatures fresh each pass by NAME -- holding a
            # stale Object reference past a bpy.data.objects.remove() call
            # (one may get eaten mid-bake) raises ReferenceError even just
            # reading .name off it, so we never reuse old references here
            alive = [bpy.data.objects[name] for name in engines if name in bpy.data.objects]
            to_remove = []

            for cobj in alive:
                species = cobj[SPECIES_KEY]
                eng = engines[cobj.name]
                max_speed = cobj.get("jelly_max_speed", default_max_speed)

                hit = nearest_relevant_object(scene, cobj, sense_radius)
                eaten_obj = None
                if hit:
                    obj, category, dist = hit
                    stimuli_seen[cobj.name][obj.name] = category
                    intensity = max(0.0, 1.0 - dist / sense_radius)
                    eng.stimulate(category, intensity)
                    if dist <= contact_radius:
                        if category == "food":
                            food_value = obj.get("jelly_food_value", 1.0)
                            eng.feed(food_value)
                            eaten_obj = obj
                        elif category == "danger":
                            damage = obj.get("jelly_damage", default_damage)
                            eng.take_damage(damage)
                    target_dir = obj.matrix_world.translation - cobj.location
                    if target_dir.length > 1e-5:
                        heading_dirs[cobj.name] = target_dir.normalized()

                danger_present = hit is not None and hit[1] == "danger"
                unclassifiable_present = hit is not None and hit[1] == "unclassifiable"

                ally_hit = nearest_conspecific(scene, cobj, sense_radius)
                if ally_hit:
                    ally_obj, ally_dist = ally_hit
                    ally_intensity = max(0.0, 1.0 - ally_dist / sense_radius)
                    own_injured = last_health[cobj.name] < 5.0
                    if own_injured and danger_present:
                        eng.sense_conspecific("protect", ally_intensity)
                        ally_dir = ally_obj.matrix_world.translation - cobj.location
                        if ally_dir.length > 1e-5:
                            heading_dirs[cobj.name] = ally_dir.normalized()  # interpose toward the ally
                    else:
                        eng.sense_conspecific("cooperate", ally_intensity)
                        if unclassifiable_present:
                            # something unidentified nearby -> school toward
                            # the ally instead of orienting on the unknown
                            # object itself (paper sec 6.2: signal/Gv)
                            ally_dir = ally_obj.matrix_world.translation - cobj.location
                            if ally_dir.length > 1e-5:
                                heading_dirs[cobj.name] = ally_dir.normalized()

                result = eng.tick()
                motion = result["motion"]
                last_health[cobj.name] = result["health"]

                if not motion["frozen"]:
                    if motion["drifting"]:
                        wobble = Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0)) * 0.2
                        step_dir = (heading_dirs[cobj.name] + wobble).normalized()
                    else:
                        sign = 1.0 if motion["heading"] >= 0 else -1.0
                        step_dir = heading_dirs[cobj.name] * sign
                    cobj.location += step_dir * (motion["speed"] * max_speed * TICK_SECONDS)
                    cobj.keyframe_insert(data_path="location", frame=frame)
                    if step_dir.length > 1e-5:
                        cobj.rotation_mode = 'QUATERNION'
                        cobj.rotation_quaternion = step_dir.to_track_quat('X', 'Z')
                        cobj.keyframe_insert(data_path="rotation_quaternion", frame=frame)

                apply_species_motion(cobj, species, motion, frame)

                logs[cobj.name].append({
                    "frame": frame, "quadrant": result["quadrant"],
                    "dominant_mode": result["dominant_mode"],
                    "heading": motion["heading"], "speed": motion["speed"],
                    "contraction": motion["contraction"], "frozen": motion["frozen"],
                    "hunger": result["hunger"], "energy": result["energy"],
                    "structural": result["structural"], "health": result["health"],
                })

                if eaten_obj is not None:
                    to_remove.append(eaten_obj)

            for obj in to_remove:
                name = obj.name
                if name in engines:  # a creature ate another creature
                    eaten_records[name] = {
                        "species": obj[SPECIES_KEY],
                        "stimuli_seen": stimuli_seen[name],
                        "log": logs[name],
                        "engine_state_end": engines[name].get_state(),
                        "eaten_at_frame": frame,
                    }
                    del engines[name]
                    del heading_dirs[name]
                bpy.data.objects.remove(obj, do_unlink=True)

            frame += ticks_per_frame_gap

        creatures_entry = dict(eaten_records)
        creatures_entry.update({
            name: {
                "species": bpy.data.objects[name][SPECIES_KEY],
                "stimuli_seen": stimuli_seen[name],
                "log": logs[name],
                "engine_state_end": eng.get_state(),
            }
            for name, eng in engines.items()
        })
        event = {
            "id": f"event{len(story['events']) + 1}",
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "creatures": creatures_entry,
        }
        story["events"].append(event)
        try:
            with open(json_path, "w") as f:
                json.dump(story, f, indent=2)
        except OSError as e:
            self.report({'WARNING'}, f"Baked OK but couldn't save story JSON: {e}")
            return {'FINISHED'}

        self.report({'INFO'}, f"Baked {event['id']} ({len(engines)} creatures) -> {json_path}")
        return {'FINISHED'}


# -- panel --------------------------------------------------------------

class JELLY_PT_panel(bpy.types.Panel):
    bl_label = "Jellyfish AI"
    bl_idname = "JELLY_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Jellyfish AI"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="New creature:")
        layout.prop(scene, "jellyfish_ai_species")
        layout.prop(scene, "jellyfish_ai_new_name")
        layout.operator("jellyfish_ai.create_rig")

        layout.separator()
        layout.label(text="Selected object:")
        row = layout.row(align=True)
        row.operator("jellyfish_ai.mark_predator")
        row.operator("jellyfish_ai.mark_food")
        layout.prop(scene, "jellyfish_ai_default_damage")

        layout.separator()
        layout.prop(scene, "jellyfish_ai_sense_radius")
        layout.prop(scene, "jellyfish_ai_contact_radius")
        layout.prop(scene, "jellyfish_ai_max_speed")
        layout.prop(scene, "jellyfish_ai_json_path")

        layout.separator()
        row = layout.row(align=True)
        row.prop(scene, "frame_start", text="Start")
        row.prop(scene, "frame_end", text="End")
        layout.operator("jellyfish_ai.bake")
        layout.label(text="Set Start/End frame per event, then Bake --")
        layout.label(text="all creature rigs react to each other AND to")
        layout.label(text="tagged objects; one JSON event covers all of them.")


# -- registration ------------------------------------------------------------

classes = (JELLY_OT_create_rig, JELLY_OT_mark_predator, JELLY_OT_mark_food, JELLY_OT_bake, JELLY_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.jellyfish_ai_species = bpy.props.EnumProperty(
        name="Species",
        items=[("jellyfish", "Jellyfish", ""), ("turtle", "Turtle", ""), ("fish", "Fish", "")],
        default="jellyfish")
    bpy.types.Scene.jellyfish_ai_new_name = bpy.props.StringProperty(
        name="Name", default="", description="Leave empty for '<Species> AI'")
    bpy.types.Scene.jellyfish_ai_sense_radius = bpy.props.FloatProperty(
        name="Sense Radius", default=8.0, min=0.1,
        description="Distance at which a creature notices another object/creature")
    bpy.types.Scene.jellyfish_ai_contact_radius = bpy.props.FloatProperty(
        name="Contact Radius", default=0.6, min=0.01,
        description="Distance at which food gets eaten / damage is applied")
    bpy.types.Scene.jellyfish_ai_max_speed = bpy.props.FloatProperty(
        name="Max Speed", default=2.0, min=0.0,
        description="Scene units/second at motion speed=1.0")
    bpy.types.Scene.jellyfish_ai_default_damage = bpy.props.FloatProperty(
        name="Default Predator Damage", default=2.0, min=0.0, max=10.0,
        description="Used for a danger object/creature with no jelly_damage property of its own")
    bpy.types.Scene.jellyfish_ai_json_path = bpy.props.StringProperty(
        name="Story JSON", default="//jellyfish_story.json", subtype='FILE_PATH',
        description="One combined event per bake (all creatures). If it already "
                     "has events, baking resumes each creature's engine from the "
                     "previous event instead of resetting it.")


def unregister():
    for prop in ("jellyfish_ai_species", "jellyfish_ai_new_name", "jellyfish_ai_sense_radius",
                 "jellyfish_ai_contact_radius", "jellyfish_ai_max_speed",
                 "jellyfish_ai_default_damage", "jellyfish_ai_json_path"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
