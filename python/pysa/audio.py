"""Sound and music: positional sound effects, mission audio, and the radio.

    from pysa import audio, player

    audio.play_sound(player.pos, 1058)       # a one-off sound at a point
    audio.set_radio(audio.RADIO.K_DST)       # switch the car radio
    audio.radio_off()

    clip = audio.MissionAudio(slot=0)
    clip.load(2)                             # load bank audio id 2
    if clip.loaded:
        clip.play()

Sound ids are the game's internal effect ids (see any SA sound-id list).
Mission audio ids index the game's audio banks.
"""
from __future__ import annotations

from .math3 import Vector3
from .native import cmd


class RADIO:
    """Radio station ids (from plugin-sdk eRadioID)."""
    PLAYBACK_FM = 1
    K_ROSE = 2
    K_DST = 3
    BOUNCE_FM = 4
    SF_UR = 5
    RADIO_LOS_SANTOS = 6
    RADIO_X = 7
    CSR_103_9 = 8
    K_JAH_WEST = 9
    MASTER_SOUNDS_98_3 = 10
    WCTR = 11
    USER_TRACKS = 12
    OFF = 13


def play_sound(pos, sound_id: int) -> None:
    """Play a one-off sound effect at a world position."""
    x, y, z = Vector3.of(pos)
    cmd.ADD_ONE_OFF_SOUND(x, y, z, int(sound_id))


def set_radio(channel: int) -> None:
    """Set the radio station (see RADIO)."""
    cmd.SET_RADIO_CHANNEL(int(channel))


def get_radio() -> int:
    return cmd.GET_RADIO_CHANNEL()


def radio_off() -> None:
    cmd.SET_RADIO_CHANNEL(RADIO.OFF)


def favourite_station() -> None:
    """Tune to the player's most-listened station."""
    cmd.SET_RADIO_TO_PLAYERS_FAVOURITE_STATION()


class MissionAudio:
    """One of the game's mission-audio slots (0 or 1)."""

    __slots__ = ("_slot",)

    def __init__(self, slot: int = 0):
        self._slot = int(slot)

    @property
    def slot(self) -> int:
        return self._slot

    def load(self, audio_id: int) -> None:
        cmd.LOAD_MISSION_AUDIO(self._slot, int(audio_id))

    @property
    def loaded(self) -> bool:
        return cmd.HAS_MISSION_AUDIO_LOADED(self._slot)

    def play(self) -> None:
        cmd.PLAY_MISSION_AUDIO(self._slot)

    @property
    def finished(self) -> bool:
        return cmd.HAS_MISSION_AUDIO_FINISHED(self._slot)

    def at(self, pos) -> None:
        """Position the audio in 3D (so it fades with distance)."""
        x, y, z = Vector3.of(pos)
        cmd.SET_MISSION_AUDIO_POSITION(self._slot, x, y, z)

    def __repr__(self) -> str:
        return f"MissionAudio(slot={self._slot})"
