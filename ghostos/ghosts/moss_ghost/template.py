from ghostos.core.moss import Moss as Stub


class Moss(Stub):
    pass


# <moss-hide>
from ghostos.ghosts.moss_ghost.impl import MossGhost, BaseMossGhostMethods

__ghost__ = MossGhost(
)


class MossAgentMethods(BaseMossGhostMethods):
    pass

# </moss-hide>
