By installing the [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) card, you can create cards to dynamically display the status of all of your zones.

#### All zones with their status, sorted by zone
```yaml
type: custom:auto-entities
card:
  type: entities
  title: All zones
filter:
  include:
    - attributes:
        zone: $$*
      options:
        state_color: true
sort:
  method: attribute
  attribute: zone
  numeric: true
```
#### Zones that are currently open
```yaml
type: custom:auto-entities
card:
  type: entities
  title: Open zones
filter:
  include:
    - attributes:
        zone: $$*
      state: on
      options:
        state_color: true
        secondary_info: last-updated
sort:
  method: attribute
  attribute: zone
  numeric: true
```

#### Zones that have been triggered in the last hour, ordered by the most recent
```yaml
type: custom:auto-entities
card:
  type: entities
  title: Recent zones
filter:
  include:
    - attributes:
        zone: $$*
        last_tripped_time: '< 1h ago'
      options:
        state_color: true
        secondary_info: last-updated
sort:
  method: last_changed
  reverse: true
```

#### Expanded information
Adding in the custom [multi entity row](https://github.com/benct/lovelace-multiple-entity-row) allows us to display additional information with each zone, like adding in the zone number underneath the friendly name or additional information, like bypassed, low battery, and tamper in the same line.

#### Zone number, bypassed, low battery, and tamper, not showing the state:
```yaml
type: custom:auto-entities
card:
  type: entities
  title: Recent zones
filter:
  template: |
    {% for s in states.binary_sensor | selectattr('attributes.zone', 'defined') -%}
       {{-
          {
            'type': 'custom:multiple-entity-row',
            'entity': s.entity_id,
            'name': s.name,
            'secondary_info': {'name':'Zone','attribute':'zone'},
            'entities': [
                {'attribute':'bypassed','name':'Bypassed'},
                {'attribute':'low_battery','name':'Low battery'},
                {'attribute':'tamper','name':'Tamper'}
            ],
            'show_state': false,
            'state_color': true
          }
        -}},
    {%- endfor %}
sort:
  method: attribute
  attribute: zone
  numeric: true
```

#### Zone number and state but without additional attributes:
```yaml
type: custom:auto-entities
card:
  type: entities
  title: Recent zones
filter:
  template: |
    {% for s in states.binary_sensor | selectattr('attributes.zone', 'defined') -%}
       {{-
          {
            'type': 'custom:multiple-entity-row',
            'entity': s.entity_id,
            'name': s.name,
            'secondary_info': {'name':'Zone','attribute':'zone'},
            'state_color': true
          }
        -}},
    {%- endfor %}
sort:
  method: attribute
  attribute: zone
  numeric: true
```
