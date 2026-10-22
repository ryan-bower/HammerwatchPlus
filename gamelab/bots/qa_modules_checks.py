"""Declared existing module checks with complete, fail-closed result accounting."""
from gamelab.bots.plan_checks import Checks


def assess(flags, required):
    missing = sorted(set(required) - set(flags))
    failed = sorted(k for k, value in flags.items() if isinstance(value, bool) and not value)
    ok = bool(required) and not missing and not failed and all(flags[k] is True for k in required)
    return dict(ok=ok, missing_required=missing, failed_flags=failed)


def run(p, sections, required_flags):
    c = Checks(p)
    for section in sections.split(","):
        try:
            getattr(c, section)()
        except Exception as exc:
            c.flag(section + "_crashed", False, repr(exc))
    c.out.update(assess(c.out, required_flags))
    c.out.update(notes=c.notes, terminal=" | ".join(c.notes)[-3000:],
                 requested_sections=sections.split(","), required_flags=required_flags)
    return c.out
