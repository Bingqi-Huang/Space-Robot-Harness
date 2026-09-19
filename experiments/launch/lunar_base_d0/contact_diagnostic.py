"""Development fixture: execute production pick only through contact and closure.

Loaded only by the temporary diagnostic manifest, never the mission palette.
The intentional failure prevents pick from asserting held without its lift test.
All commands retain the ordinary runner/safety/HAL path.
"""
from openral_rskill._eye_in_hand import StageFailure
from openral_rskill.procedural_pick import PickRskill


class ContactDiagnosticPick(PickRskill):
    def hold(self, jaw_closed: float) -> None:
        self._evidence['contact_diagnostic'] = {
            'jaw_closed_rad': jaw_closed,
            'image': self.save('contact_closed.png', self.lit_frame().bgr),
            'lift_executed': False,
            'bring_in_executed': False,
        }
        raise StageFailure('contact_diagnostic_complete',
                           'development fixture stopped after closure; held is not established',
                           local_retry=False)
