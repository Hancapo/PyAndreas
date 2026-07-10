"""OOP PyAndreas port of the CLEO MSPARK effect.

Activate on foot with L1 + D-pad Down. Aim with the left stick, keep L1 held
to discharge repeatedly, and release it to tear the effect down.

This is intentionally organized as a Python effect object rather than as a
translation of CLEO labels and local variables. The visual behavior remains:
an attached beam rig, animated checkpoints, colored coronas, ground smoke,
dynamic lights, mission audio, a camera target, and sequenced explosions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pysa
from pysa import (CAMERA_MODE, MISSION_AUDIO_SLOT, VEHICLE, GameObject,
                  PedAnimationClip, ScriptSession, Vehicle, fx, hud, pad,
                  player, world)
from pysa.audio import MissionAudio
from pysa.markers import CHECKPOINT, Checkpoint
from pysa.math3 import Vector3
from pysa.pad import BUTTON


@dataclass(frozen=True)
class SparkConfig:
    """Tunable parts of the effect, kept separate from runtime state."""

    object_model: int = 1582
    audio_id: int = 6402
    audio_slot: MISSION_AUDIO_SLOT = MISSION_AUDIO_SLOT.SLOT3
    minimum_active_ms: int = 750
    camera_distance: float = 7.0


class MasterSpark:
    """Owns the complete lifecycle and rendering state of one MSPARK effect."""

    checkpoint_colors = (
        (255, 128, 128, 64),
        (255, 192, 128, 64),
        (255, 255, 128, 64),
        (128, 255, 128, 64),
        (128, 128, 255, 64),
        (128, 128, 192, 64),
        (192, 128, 255, 64),
        (255, 128, 128, 64),
    )
    spiral_colors = (
        ((255, 0, 0),) * 8 +
        ((0, 255, 0),) * 8 +
        ((0, 0, 255),) * 8 +
        ((255, 255, 0),) * 7 +
        ((0, 255, 255),) * 7 +
        ((255, 0, 255),) * 7
    )
    white_beam = (
        (0.85, 0.25),
        (1.0, 0.5),
        (1.5, 1.0),
        (2.25, 1.5),
        (3.25, 2.0),
        (4.5, 2.5),
        (6.0, 3.0),
        (7.75, 3.5),
    )
    explosion_paths = {
        0: (12.0, 22.0, 32.0, 42.0),
        1: (49.5, 39.5, 29.5, 19.5),
        2: (17.0, 27.0, 37.0, 47.0),
        3: (44.5, 34.5, 24.5, 14.5),
    }

    def __init__(self, config: SparkConfig = SparkConfig()):
        self.config = config
        self.audio = MissionAudio(config.audio_slot)
        self.target: GameObject | None = None
        self.camera_vehicle: Vehicle | None = None
        self.checkpoints: list[Checkpoint] = []
        self.session: ScriptSession | None = None
        self.animation: PedAnimationClip | None = None
        self.heading = 0.0
        self.pitch = 0.0
        self.spin = 0.0
        self.counter_spin = 0.0
        self.charge_ms = 0
        self.pattern = 0
        self.started_at = 0
        self.previous_frame = 0

    @property
    def can_activate(self) -> bool:
        """Whether the player and controller are in a valid activation state."""
        return (player.playing and player.ped.on_foot and
                player.missions.can_start and pad.pressed(BUTTON.L1) and
                pad.pressed(BUTTON.DPAD_DOWN))

    @property
    def active(self) -> bool:
        """Keep the startup animation alive briefly even if L1 is released."""
        elapsed = pysa.game_time() - self.started_at
        return pad.pressed(BUTTON.L1) or elapsed < self.config.minimum_active_ms

    def run(self):
        """Long-lived script coroutine: wait, activate, clean up, repeat."""
        hud.help_text("MSPARK ready: hold L1 + D-pad Down")
        while True:
            if self.can_activate:
                yield from self.activate()
            yield

    def activate(self):
        """Build and run one effect session with guaranteed cleanup."""
        with ScriptSession() as self.session:
            self.session.disable_vital_stats_button()
            try:
                yield from self._setup()
                while self.active:
                    self._frame()
                    yield
            finally:
                self.close()

    def _setup(self):
        session = self._session()
        session.track(self.audio)
        self.audio.load(self.config.audio_id)
        while not self.audio.loaded:
            yield

        ped = player.ped
        self.animation = ped.anim.play(
            "GunMove_BWD", "PED", blend=4.0, loop=True, lock_x=True,
            lock_y=True, keep_last_frame=True, interruptible=False)

        self.target = session.spawn_object(self.config.object_model, ped.pos)
        self.target.collision(False)
        self.target.visible(False)
        self.target.make_proof()
        self._attach_target()

        self.camera_vehicle = session.spawn_vehicle(
            VEHICLE.SPARROW, ped.offset((0.0, 0.0, -50.0)))
        self.camera_vehicle.attach_to_object(
            self.target, offset=(0.0, self.config.camera_distance, 0.0))
        self.camera_vehicle.make_proof()
        self.camera_vehicle.visible(False)
        self.camera_vehicle.collision(False)
        self.camera_vehicle.engine_broken = False
        session.camera.point_at(
            self.camera_vehicle, CAMERA_MODE.CAM_ON_A_STRING)

        self.checkpoints = self._create_checkpoints()
        self.audio.play()
        self.started_at = self.previous_frame = pysa.game_time()
        self.heading = ped.heading
        self.pitch = self.spin = self.counter_spin = 0.0
        self.charge_ms = 500
        self.pattern = 0

    def _frame(self) -> None:
        """Advance controls, animation, visuals and discharge for one frame."""
        target = self._target()
        ped = player.ped
        now = pysa.game_time()
        delta_ms = max(0, now - self.previous_frame)
        self.previous_frame = now
        self.charge_ms += delta_ms
        self._update_aim(delta_ms)

        if self.animation is not None:
            self.animation.playing = False
            self.animation.time = 0.27
        ped.heading = self.heading
        camera.shake(250)
        self._attach_target()
        ped.tasks.look_at_coord(target.offset((0.0, 49.5, 0.0)), 999999)

        self._draw_beam()
        self._draw_spirals()
        self._animate_checkpoints()
        self._attach_target()
        self._draw_lights()

        if self.charge_ms >= 100:
            self.charge_ms = 0
            self._discharge()

    def _update_aim(self, delta_ms: int) -> None:
        stick = pad.left_stick_direction()
        self.heading += -stick.x * delta_ms / 20.0
        self.pitch = max(-15.0, min(
            45.0, self.pitch + stick.y * delta_ms / 20.0))
        self.spin += delta_ms * 0.36
        self.counter_spin -= delta_ms * 0.18

    def _attach_target(self, spin: float = 0.0) -> None:
        self._target().attach_to_ped(
            player.ped, offset=(0.0, 0.5, 0.0),
            rotation=(self.pitch, spin, 0.0))

    def _create_checkpoints(self) -> list[Checkpoint]:
        target = self._target()
        checkpoints = []
        for index, color in enumerate(self.checkpoint_colors):
            distance = 4.5 + index * 5.0
            radius = 2.25 if index == 0 else (3.25 if index == 1 else 3.75)
            checkpoint = Checkpoint(
                target.offset((0.0, distance, 0.0)),
                kind=CHECKPOINT.TORUS,
                points_to=target.offset((0.0, 50.0, 0.0)),
                radius=radius,
            )
            checkpoint.color = color
            checkpoints.append(self._session().track(checkpoint))
        return checkpoints

    def _draw_beam(self) -> None:
        target = self._target()
        for distance, size in self.white_beam:
            fx.weaponshop_corona(target.offset((0.0, distance, 0.0)),
                                 size=size)

    def _draw_spirals(self) -> None:
        target = self._target()
        color_index = 0
        for arm in range(6):
            rotation = arm * 120.0 + self.spin + (60.0 if arm >= 3 else 0.0)
            self._attach_target(rotation)

            accents = (7.5, 12.0) if arm < 3 else (9.75,)
            for distance in accents:
                color = self.spiral_colors[color_index]
                color_index += 1
                size = 3.5 if distance < 9.0 else 4.5
                z = 0.7 if distance < 9.0 else 0.9
                fx.weaponshop_corona(target.offset((0.0, distance, z)), size,
                                     color, fx.CORONA.STAR)

            distance = 17.0 if arm < 3 else 14.5
            while distance < 44.5:
                color = self.spiral_colors[color_index]
                color_index += 1
                fx.weaponshop_corona(target.offset((0.0, distance, 1.0)),
                                     4.5, color, fx.CORONA.STAR)
                distance += 5.0

    def _animate_checkpoints(self) -> None:
        target = self._target()
        for index, checkpoint in enumerate(self.checkpoints):
            distance = 4.5 + index * 5.0
            angle = index * 150.0 + self.counter_spin
            self._attach_target(angle)
            pos = target.offset((0.0, distance, 0.0))
            end = target.offset((0.0, distance - 1.5, 0.2))
            direction = (end - pos).normalized() * 0.5
            alpha = int(abs(angle % 360.0 - 180.0) / 180.0 * 64.0 + 16.0)
            red, green, blue, _ = self.checkpoint_colors[index]
            checkpoint.update_visual(pos, direction,
                                     (red, green, blue, alpha))

    def _draw_lights(self) -> None:
        target = self._target()
        for distance in range(5, 156, 10):
            fx.light(target.offset((0.0, float(distance), 0.0)), radius=25.0)

    def _discharge(self) -> None:
        """Emit the ground smoke and the current staged explosion pattern."""
        self._draw_ground_smoke()
        base_pattern = self.pattern - 4 if self.pattern >= 4 else self.pattern
        for distance in self.explosion_paths.get(base_pattern, ()):
            world.explosion_no_sound(
                self._target().offset((0.0, distance, 0.0)),
                world.EXPLOSION.MINE)
        self.pattern = base_pattern + 5
        if self.pattern == 8:
            self.pattern = 4

    def _draw_ground_smoke(self) -> None:
        target = self._target()
        self._attach_target()
        distance = 2.0
        for index in range(7):
            angle = math.radians(index * 15.0)
            origin = target.offset((0.0, 0.0, 0.0))
            for side in (2.5, -2.5):
                radial_x = math.sin(angle) * (25.0 if side > 0 else -25.0)
                radial_y = math.cos(angle) * -25.0
                velocity = target.offset((radial_x, radial_y, 0.0)) - origin
                self._smoke_at(side, distance, velocity)
            distance += 2.5

        distance = 17.0
        origin = target.offset((0.0, 0.0, 0.0))
        right = target.offset((25.0, 0.0, 0.0)) - origin
        left = target.offset((-25.0, 0.0, 0.0)) - origin
        for _ in range(19):
            self._smoke_at(2.5, distance, right)
            self._smoke_at(-2.5, distance, left)
            distance += 2.5

    def _smoke_at(self, side: float, distance: float,
                  velocity: Vector3) -> None:
        probe = self._target().offset((side, distance, 0.0)) + (0.0, 0.0, 5.0)
        ground = world.ground_z(probe.x, probe.y, probe.z)
        alpha = (ground - probe.z) * 0.1 + 1.5
        if alpha > 0.0:
            fx.smoke_particle((probe.x, probe.y, ground + 0.5), velocity,
                              alpha=alpha, size=0.5, fade=0.025)

    def close(self) -> None:
        """Idempotently release every game resource owned by the effect."""
        if self.session is not None:
            self.session.close()
        self.checkpoints.clear()
        if player.playing:
            player.ped.freeze(False)
            player.ped.tasks.clear()
        self.target = None
        self.camera_vehicle = None
        self.animation = None
        self.session = None

    def _target(self) -> GameObject:
        if self.target is None:
            raise RuntimeError("MSPARK target is not active")
        return self.target

    def _session(self) -> ScriptSession:
        if self.session is None:
            raise RuntimeError("MSPARK session is not active")
        return self.session


effect = MasterSpark()


@pysa.script
def mspark():
    yield from effect.run()
