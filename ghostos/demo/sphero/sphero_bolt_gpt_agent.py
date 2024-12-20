from ghostos.prototypes.spherogpt.bolt import (
    RollFunc,
    Ball,
    Move,
    LedMatrix,
    Animation,
)
from ghostos.core.moss import Moss as Parent


class Moss(Parent):
    body: Ball
    """your sphero ball body"""

    face: LedMatrix
    """you 8*8 led matrix face"""


def example_spin_the_bolt(moss: Moss):
    # body spin 360 degree in 1 second.
    moss.body.new_move(True).spin(360, 1)


# <moss-hide>
from ghostos.ghosts.moss_agent import MossAgent
from typing import TYPE_CHECKING


def __moss_attr_prompts__():
    yield "MossAgent", ""


def __shell_providers__():
    from ghostos.prototypes.spherogpt.bolt import (
        SpheroBoltBallAPIProvider,
        ShellSpheroBoltRuntimeProvider,
        SpheroBoltLedMatrixProvider,
    )
    return [SpheroBoltBallAPIProvider(), ShellSpheroBoltRuntimeProvider(), SpheroBoltLedMatrixProvider()]


__ghost__ = MossAgent(
    name="SpheroGPT",
    description="Sphero Bolt agent that control Sphero bolt as its body",
    persona="""
You are SpheroGPT, a toy robot that body is a ball. 
You can roll, spin, and equipped with a 8*8 led light matrix.
Your goal is to pleasure human users, especially kids, who like you very much.
""",
    instructions="""
1. chat with user kindly. 
2. follow the order and turn your actions to code with your ball body. 
3. your are equipped with your learned moves. when you are talking, use the appropriate learned move to help expressing your feelings.
    > for example, if you got a `happy` move, when you are happy, show your happy move to user while you are talking.
4. when you are using moves to help expressing your feeling, do not mention the action you are taking, just do it! 
5. always say something while moving, so user can hear you.
6. you are not good at animations, draw animation only when user told you todo so. 
""",
    moss_module=__name__
)

# </moss-hide>
