"""Regression checks for the mixed d100 camera and stable player header.

This suite is intentionally Qt-free; actual visual rendering still requires
opening the application on Windows with its WebEngine dependencies.
"""
from pathlib import Path
import math
import unittest

ROOT = Path(__file__).resolve().parent
PHYSICS = (ROOT / 'd100_physics.js').read_text(encoding='utf-8')
HUB = (ROOT / 'campaign_role_ui.py').read_text(encoding='utf-8')


class D100MixedSizing(unittest.TestCase):
    def test_mixed_camera_fits_one_die_and_tracks_its_real_body(self):
        # The old formula used min(1, camera.aspect) in the distance and
        # shrank a die in a tall, narrow mixed-roll tray.
        mixed_branch = PHYSICS.split('if (mixed && quantity === 1) {',1)[1].split('} else {',1)[0]
        self.assertIn('diameterPx', mixed_branch)
        self.assertIn('context.mixedCameraDistance', mixed_branch)
        self.assertNotIn('Math.min(1, camera.aspect)', mixed_branch)
        self.assertIn('dieInstances[0].body.position', PHYSICS)
        self.assertIn('camera.lookAt(focus)', PHYSICS)

    def test_mixed_diameter_is_stable_across_reasonable_canvas_sizes(self):
        radius = 1.05
        tan_half_fov = math.tan(math.radians(43 / 2))
        for w, h in [(144, 282), (160, 282), (200, 282), (125, 190), (220, 340)]:
            target = max(40, min(118, w * .72, h * .49))
            distance = max(radius * 3.5, radius * h / (target * tan_half_fov))
            apparent_px = radius * h / (distance * tan_half_fov)
            # 28% side margins keep the single body comfortably in frame.
            self.assertLessEqual(apparent_px, w * .75)
            self.assertGreater(apparent_px, 65 if w > 130 else 40)

    def test_regular_d100_and_physics_results_unchanged(self):
        self.assertIn('camera.position.set(0, extent / Math.min(1, camera.aspect)', PHYSICS)
        self.assertIn('instance.value=candidate.value;', PHYSICS)
        self.assertIn('linearDamping:.50,angularDamping:.75', PHYSICS)


class PlayerHeaderLayout(unittest.TestCase):
    def test_heading_and_description_are_above_scrollable_details(self):
        player = HUB.split('def _build_player_page(self):',1)[1].split('def _open_linked_player_character',1)[0]
        self.assertIn('self.player_header = QWidget()', player)
        self.assertIn('right_box.addWidget(self.player_header, 0, Qt.AlignmentFlag.AlignTop)', player)
        self.assertIn('header_layout.addWidget(self.player_name_label)', player)
        self.assertIn('header_layout.addWidget(self.player_explainer)', player)
        self.assertNotIn('overview_layout.addWidget(self.player_name_label)', player)
        self.assertNotIn('overview_layout.addWidget(self.player_explainer)', player)
        self.assertLess(player.index('right_box.addWidget(self.player_header'),
                        player.index('self.player_detail_stack = QStackedWidget()'))
        self.assertIn('self.player_overview_scroll = self._scrollable_panel(overview_page)', player)

    def test_existing_titles_and_behavior_kept(self):
        self.assertIn('"No player campaigns yet"', HUB)
        self.assertIn('self.player_name_label.setText(str(campaign.get("name")', HUB)
        self.assertIn('self.player_explainer.setText(', HUB)
        self.assertIn('overview_layout.insertWidget(0, self.player_join_form)', HUB)


if __name__ == '__main__':
    unittest.main()
