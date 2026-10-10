"""What the plugin logs: failures when they start, change or end.

The owner decided on 2026-10-10 that a listener failing at every push must not log at every push
(v3 did), and that logs show only a listener's scheme, host and port, since the path or the query
of a push URL carries the monitor's push token (v3 logged whole URLs): ``xincord.plugins.redaction``
cuts URLs to their origins.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123
"""

from dataclasses import dataclass, field

STEADY = 3  # successes in a row that end a failure episode


@dataclass
class Failures:
    """One step of a listener (its pushes, or its pings) and its failure episode, if one is open.

    An episode starts with a failure and ends once the step has worked ``STEADY`` times in a row.
    Only a failure whose kind (a status code or an error type) is new in the episode is logged at
    its level, so that a listener that fails at every push, alternates two kinds of failure or
    fails at every other push does not log at every push; the others go to the debug level.
    """

    kinds: set[object] = field(default_factory=set[object])  # the kinds logged in the episode
    count: int = 0  # the episode's failures; 0 while none is open
    streak: int = 0  # the successes in a row since the episode's last failure

    def fail(self, kind: object) -> bool:
        """Count a failure of ``kind``; return whether its kind is new in the episode."""
        self.count += 1
        self.streak = 0
        if kind in self.kinds:
            return False
        self.kinds.add(kind)
        return True

    def succeed(self) -> int:
        """Count a success; return the episode's failures when this success ends it, else 0."""
        if not self.count:
            return 0
        self.streak += 1
        if self.streak < STEADY:
            return 0
        count = self.count
        self.kinds = set()
        self.count = 0
        self.streak = 0
        return count
