"""Optional in-game smoke tests for the built-in developer console.

Enable it in ``PyAndreas.ini`` or Pause Menu > Options > PyAndreas. Copy
this file into ``PyAndreas/scripts`` only if you want these example tests,
then type ``tests`` in the built-in F10 console.
"""
from pysa import ScriptSession, VEHICLE, dev_test, player, world


@dev_test("player wrapper is live")
def player_wrapper_is_live():
    assert player.playing, "load a save or start a game first"
    assert player.ped.exists, "player ped has no valid pool handle"


@dev_test("world collections contain usable wrappers")
def world_collections_are_usable():
    for vehicle in world.vehicles:
        assert vehicle.exists, f"invalid vehicle wrapper: {vehicle!r}"
    for ped in world.peds:
        assert ped.exists, f"invalid ped wrapper: {ped!r}"


@dev_test("temporary vehicle survives a delayed command")
def delayed_vehicle_command():
    assert player.playing, "load a save or start a game first"
    with ScriptSession() as session:
        position = player.ped.offset((4.0, 6.0, 1.0))
        vehicle = session.spawn_vehicle(VEHICLE.GREENWOO, position)
        yield 250
        assert vehicle.exists, "spawned vehicle disappeared during wait"
        vehicle.pos = player.ped.offset((6.0, 8.0, 1.0))
        yield 100
        assert vehicle.exists, "vehicle became invalid after teleport"
