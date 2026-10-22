"""Controlled native key gates and actual chest item payloads; no co-op claim.

Uses existing IUsable.CanUse, exact unit identity, Pilot's native interaction,
and read-only item type/quality fields. Spawn/teleport and forced chance endpoints
are fixtures. Neither natural lock probability nor ordinary acquisition is proved.
"""
import math
import re
import time

from gamelab.bots.plan_checks import Checks
from gamelab.bots.qa_modules_checks import assess


REQUIRED = ['mission_started']
REQUIRED += ['bronze_' + name for name in (
    'spawned', 'zero_keys', 'native_refusal', 'refusal_unchanged', 'key_ready',
    'opened', 'key_consumed', 'native_gear')]
for _label in ('legendary', 'epic'):
    REQUIRED += [_label + '_' + name for name in (
        'spawned', 'key_ready', 'opened', 'key_consumed', 'native_bonus', 'native_base')]


class KeyChecks(Checks):
    def __init__(self, p):
        super().__init__(p)
        self.records = []

    def counts(self):
        log = self.hwp('keys', 0.3, until='party pool')
        own = re.findall(r'Keys: bronze (\d+), silver (\d+), gold (\d+), ace (\d+)', log)
        pool = re.findall(r'party pool bronze (\d+) silver (\d+) gold (\d+) ace (\d+)', log)
        return dict(valid=bool(own and pool), own=list(map(int, own[-1])) if own else [],
                    pool=list(map(int, pool[-1])) if pool else [], native_log=log[-1200:])

    def key_count(self, counts, index):
        return (counts['valid'] and counts['own'][index],
                counts['valid'] and counts['pool'][index])

    def ground(self):
        reply = self.gl('items', 220)
        valid = (reply.get('ok') is True and reply.get('truncated') == 0
                 and reply.get('count') == len(reply.get('items', [])))
        return reply, valid

    def chest(self, uid):
        reply = self.gl('near', 360, 'items/chests/chest_')
        units = [u for u in reply.get('units', []) if u.get('unit') == uid]
        return reply.get('ok') is True and reply.get('truncated') == 0, units

    def usable(self, uid):
        reply = self.gl('usables')
        entry = next((x for x in reply.get('usables', []) if x.get('unit', {}).get('unit') == uid), None)
        return reply, entry

    def spawn_chest(self, label, tier):
        dx, dy = self.chest_spot()
        before = self.gl('near', 360, 'items/chests/chest_')
        before_ids = {u['unit'] for u in before.get('units', [])}
        spawn = self.gl('spawn', 'items/chests/chest_' + tier + '_equipment.unit', dx, dy)
        time.sleep(0.9)
        after = self.gl('near', 360, 'items/chests/chest_')
        fresh = [u for u in after.get('units', []) if u['unit'] not in before_ids]
        if (spawn.get('ok') is not True or before.get('truncated') != 0
                or after.get('truncated') != 0 or len(fresh) != 1):
            self.flag(label + '_spawned', False, str(dict(spawn=spawn, before=before, after=after)))
            return None
        target = fresh[0]
        self.gl('teleport', target['x'], target['y'] + 20)
        time.sleep(0.5)
        plr = self.gl('state').get('player', {})
        reply, entry = self.usable(target['unit'])
        near = (isinstance(plr.get('x'), (int, float)) and isinstance(plr.get('y'), (int, float))
                and math.hypot(plr['x'] - target['x'], plr['y'] - target['y']) <= 30)
        valid = (near and reply.get('ok') is True and entry is not None
                 and target.get('behavior') == 'HWPChest')
        self.flag(label + '_spawned', valid, str(dict(target=target, actual_player=plr, usable=entry)))
        return target if valid else None

    def grant_and_open(self, label, target, key, index, before_counts):
        self.hwp('keygive ' + key + ' 1', 0.4, until='key(s)')
        counts = self.counts()
        reply, entry = self.usable(target['unit'])
        ready = (before_counts['valid'] and self.key_count(before_counts, index) == (0, 0)
                 and counts['valid'] and self.key_count(counts, index) == (1, 0)
                 and reply.get('ok') is True and entry is not None
                 and entry.get('canUse') is True and entry.get('top') is True)
        self.flag(label + '_key_ready', ready, str(dict(before=before_counts, after=counts, usable=entry)))
        if not ready:
            return None
        ground0, valid0 = self.ground()
        interaction = self.p.use(target['unit'], timeout=20)
        time.sleep(2.5)
        complete, remaining = self.chest(target['unit'])
        after_counts = self.counts()
        ground1, valid1 = self.ground()
        self.flag(label + '_opened', complete and not remaining,
                  str(dict(result=interaction.result, reason=interaction.reason, remaining=remaining)))
        self.flag(label + '_key_consumed', after_counts['valid']
                  and self.key_count(after_counts, index) == (0, 0), str(after_counts))
        old_ids = {x['unit'] for x in ground0.get('items', [])}
        fresh = [x for x in ground1.get('items', []) if x['unit'] not in old_ids
                 and x.get('picked') is False and x.get('hidden') is False]
        payload = dict(label=label, target=target, before=ground0, after=ground1,
                       complete=valid0 and valid1, fresh=fresh, key_before=counts, key_after=after_counts,
                       interaction=dict(result=interaction.result, reason=interaction.reason))
        self.records.append(payload)
        self.g.shot('keys-' + label + '-opened')
        return payload

    def bronze(self):
        target = self.spawn_chest('bronze', 'bronze')
        if target is None:
            return
        counts0 = self.counts()
        self.flag('bronze_zero_keys', counts0['valid'] and self.key_count(counts0, 0) == (0, 0), str(counts0))
        reply, entry = self.usable(target['unit'])
        self.flag('bronze_native_refusal', reply.get('ok') is True and entry is not None
                  and entry.get('canUse') is False, str(entry))
        before, valid0 = self.ground()
        self.g.shot('keys-bronze-no-key')
        time.sleep(0.8)
        complete, remaining = self.chest(target['unit'])
        after, valid1 = self.ground()
        counts1 = self.counts()
        ids0 = {x['unit'] for x in before.get('items', [])}
        ids1 = {x['unit'] for x in after.get('items', [])}
        self.flag('bronze_refusal_unchanged', complete and len(remaining) == 1 and valid0 and valid1
                  and ids0 == ids1 and counts0['valid'] and counts1['valid']
                  and counts0['own'] == counts1['own'] and counts0['pool'] == counts1['pool'])
        payload = self.grant_and_open('bronze', target, 'bronze', 0, counts1)
        if payload:
            self.flag('bronze_native_gear', payload['complete'] and any(
                x.get('equipment') is True for x in payload['fresh']), str(payload['fresh']))

    def ace(self, legendary):
        label = 'legendary' if legendary else 'epic'
        self.hwp('set keys.ace_chance 1')
        self.hwp('set keys.legendary_chance ' + str(int(legendary)))
        target = self.spawn_chest(label, 'gold')
        if target is None:
            return
        payload = self.grant_and_open(label, target, 'ace', 3, self.counts())
        if not payload:
            return
        gear = [x for x in payload['fresh'] if x.get('equipment') is True]
        red = [x for x in gear if str(x.get('quality', '')).lower() == 'legendary']
        purple = [x for x in gear if str(x.get('quality', '')).lower() == 'epic']
        bonus = len(red) == 1 and len(purple) == 0 if legendary else len(purple) == 1 and len(red) == 0
        self.flag(label + '_native_bonus', payload['complete'] and bonus, str(gear))
        base = [x for x in payload['fresh'] if x.get('trinket') is True
                and str(x.get('quality', '')).lower() == 'epic']
        self.flag(label + '_native_base', payload['complete'] and len(base) == 1, str(base))


def run(p, **_):
    c = KeyChecks(p)
    c.hwp('set keys.debug 1')
    c.hwp('set keys.lock_chance 1')
    c.hwp('set keys.ace_chance 0')
    c.flag('mission_started', c.start_floor(0))
    if c.out['mission_started']:
        c.gl('cull')
        for name, call in [('bronze', c.bronze), ('legendary', lambda: c.ace(True)), ('epic', lambda: c.ace(False))]:
            try:
                call()
            except Exception as exc:
                c.flag(name + '_crashed', False, repr(exc))
    c.out.update(assess(c.out, REQUIRED))
    c.out.update(records=c.records, notes=c.notes, required_flags=REQUIRED,
                 terminal=' | '.join(c.notes)[-3000:],
                 scope='Controlled native CanUse false-to-true key gate and actual chest item type/quality. No negative-button-input, natural probability, ordinary acquisition, co-op instancing, or save lifecycle claim.')
    return c.out
