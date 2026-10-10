"""Failure episodes: a step that keeps failing logs each kind of failure once, not at every pass.

The owner decided on 2026-10-10 that a listener failing at every push must not log at every push
(UptimeHeartbeat); NtustAnnouncements' boards and Gemini attempts follow the same rule. This
package is no plugin: it has no entry point, and the plugins that use it import it.
"""

from dataclasses import dataclass, field

STEADY = 3  # successes in a row that end a failure episode


@dataclass
class Failures:
    """One repeated step (a listener's pushes, a board's page) and its failure episode, if open.

    An episode starts with a failure and ends once the step has worked ``STEADY`` times in a row.
    Only a failure whose kind (a status code or an error type) is new in the episode is logged at
    its level, so that a step that fails at every pass, alternates two kinds of failure or fails
    at every other pass does not log at every pass; the others go to the debug level.
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
