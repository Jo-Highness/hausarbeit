"""Sensor-Entitäten."""

from __future__ import annotations

from custom_components.hausarbeit.const import PERIOD_WEEK


def _find_state(hass, **attr_match):
    for state in hass.states.async_all("sensor"):
        if all(state.attributes.get(k) == v for k, v in attr_match.items()):
            return state
    return None


async def test_person_sensor_state_counts(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Alice")
    t = coordinator.add_task("Spülen")
    await hass.async_block_till_done()

    st = _find_state(hass, person_id=p["id"])
    assert st is not None
    assert st.state == "0"

    coordinator.log_execution(p["id"], t["id"])
    await hass.async_block_till_done()

    st = _find_state(hass, person_id=p["id"])
    assert st.state == "1"
    assert st.attributes["total"] == 1
    assert st.attributes["stats_days"] == 90


async def test_target_sensor_attributes(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Bob")
    t = coordinator.add_task("Wischen")
    tgt = coordinator.set_target(p["id"], t["id"], PERIOD_WEEK, 3)
    await hass.async_block_till_done()

    st = _find_state(hass, target_id=tgt["id"])
    assert st is not None
    assert st.attributes["soll"] == 3
    assert st.attributes["ist"] == 0
    assert st.attributes["rest"] == 3
    assert st.attributes["erfuellungsgrad"] == 0.0
    assert "im_soll" in st.attributes
    assert st.state == "0"

    coordinator.log_execution(p["id"], t["id"])
    await hass.async_block_till_done()
    st = _find_state(hass, target_id=tgt["id"])
    assert st.attributes["ist"] == 1
    assert st.attributes["rest"] == 2


async def test_sensors_removed_after_delete(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Carla")
    await hass.async_block_till_done()
    assert _find_state(hass, person_id=p["id"]) is not None

    coordinator.remove_person(p["id"])
    await hass.async_block_till_done()

    st = _find_state(hass, person_id=p["id"])
    # Entität entfernt oder als unavailable markiert
    assert st is None or st.state == "unavailable"


async def test_lastdone_sensor_exists(setup_integration, hass):
    _entry, coordinator = setup_integration
    p = coordinator.add_person("Dora")
    t = coordinator.add_task("Fegen")
    await hass.async_block_till_done()

    st = _find_state(hass, task_id=t["id"])
    assert st is not None  # TaskLastDoneSensor (kein Ereignis -> unknown)

    coordinator.log_execution(p["id"], t["id"])
    await hass.async_block_till_done()
    st = _find_state(hass, task_id=t["id"])
    assert st.attributes.get("person_name") == "Dora"
