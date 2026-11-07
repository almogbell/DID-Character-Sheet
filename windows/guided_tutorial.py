from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Optional, Union

from PySide6.QtCore import (
    QEvent, QObject, QPoint, QRect, Qt, QTimer, 
)
from PySide6.QtGui import (
    QColor, QMouseEvent, QPainter, QPainterPath, QPen, QRegion, QTextDocument
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
    QVBoxLayout, QWidget, QSizePolicy,
)

from ui_theme import set_themed_stylesheet
import ui_theme as ui_theme_module

from backend_2_1 import (
    STAT_NAMES,
    STAT_POINT_COSTS,
)


@dataclass
class TutorialStep:
    title: str
    text: str
    target: Callable[[], Optional[QWidget]]
    spotlight_width: int = 4
    
    advance_on_click: bool = False
    allow_next: bool = True

    # Player must actually complete something.
    require_action: bool = False

    # Checked automatically while this step is active
    completion_check: Optional[
        Callable[[], bool]
    ] = None

    # Allow normal interaction with the highlighted area.
    allow_interaction: bool = False

    before_show: Optional[Callable[[], None]] = None
    after_complete: Optional[Callable[[], None]] = None
    padding: int = 0
    tight_to_text: bool = False
    
@dataclass
class TutorialDialogStep:
    title: str
    text: str

    dialog_getter: Callable[
        [],
        Optional[QDialog],
    ]

    target_getter: Callable[
        [QDialog],
        Optional[QWidget],
    ]

    open_dialog: Optional[
        Callable[
            [],
            Optional[QDialog],
        ]
    ] = None

    require_action: bool = False

    completion_check: Optional[
        Callable[[], bool]
    ] = None

    before_show: Optional[
        Callable[[], None]
    ] = None

    after_complete: Optional[
        Callable[[], None]
    ] = None

    interaction_mode: str = "none"
    padding: int = 10

    spotlight_width: int = 4
    spotlight_radius: int | None = None

    advance_on_enter: bool = False

    card_outside_dialog: bool = False
    float_card_outside: bool = False
    
@dataclass
class TutorialMenuStep:
    """
    A tutorial step for an action that normally appears
    inside the Tools menu.
    """

    title: str
    text: str
    action_text: str

    require_action: bool = False

    completion_check: Optional[
        Callable[[], bool]
    ] = None

    before_show: Optional[
        Callable[[], None]
    ] = None

    after_complete: Optional[
        Callable[[], None]
    ] = None


TutorialAnyStep = Union[
    TutorialStep,
    TutorialMenuStep,
    TutorialDialogStep,
]


class SpotlightBorderLayer(QWidget):
    """Paint the tutorial outline independently from the masked overlay."""

    def __init__(self, parent):
        super().__init__(parent)

        self.highlight_rect = QRect()
        self.highlight_radius = 12
        self.pen_width = 4

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.hide()

    def set_spotlight(
        self,
        rect,
        radius,
        pen_width=4,
    ):
        self.highlight_rect = QRect(rect)
        self.highlight_radius = max(0, int(radius))
        self.pen_width = max(1, int(pen_width))

        if self.highlight_rect.isNull():
            self.hide()
            return

        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        if self.highlight_rect.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        outline_color = (
            "#ffffff"
            if ui_theme_module.CURRENT_THEME == "dark"
            else "#000000"
        )

        pen = QPen(
            QColor(outline_color),
            self.pen_width,
        )
        pen.setJoinStyle(
            Qt.PenJoinStyle.RoundJoin
        )
        pen.setCapStyle(
            Qt.PenCapStyle.RoundCap
        )

        painter.setPen(pen)
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        painter.drawRoundedRect(
            self.highlight_rect,
            self.highlight_radius,
            self.highlight_radius,
        )


class SpotlightOverlay(QWidget):
    def __init__(
        self,
        host: QWidget,
        controller: "GuidedTutorial",
    ):
        super().__init__(host)

        self.host = host
        self.active_host = host
        self.controller = controller
        self.target_widget: Optional[QWidget] = None
        self.highlight_rect = QRect()
        self.highlight_radius = 12

        # One identical tutorial-outline thickness everywhere.
        self.highlight_pen_width = 4

        # Sibling of the overlay, so the overlay's interaction mask
        # cannot clip the black outline.
        self.border_layer = SpotlightBorderLayer(
            host
        )

        self.setMouseTracking(True)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False,
        )
        self.hide()

        self.card = QFrame(self)
        self.card.setObjectName("TutorialCard")
        set_themed_stylesheet(
            self.card,
            """
            QFrame#TutorialCard {
                background-color: #fffaf0;
                border: 1px solid #c79a3b;
                border-radius: 16px;
            }

            QLabel {
                background: transparent;
                border: none;
                color: #25190f;
                font-family: Georgia;
            }

            QPushButton {
                background-color: #fffdf7;
                border: 1px solid #c79a3b;
                border-radius: 9px;
                padding: 5px 11px;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 800;
                color: #4f3b18;
            }

            QPushButton:hover {
                background-color: #fff4df;
                border-color: #a87824;
                color: #25190f;
            }

            QPushButton:pressed {
                background-color: #f5ead2;
            }

            QPushButton:disabled {
                background-color: #eee9df;
                border-color: #d8ccb5;
                color: #9b9388;
            }
            """,
        )

        layout = QVBoxLayout(self.card)
        # Keep the card compact. The previous 13px top/bottom margins
        # plus 7px between every row created a lot of empty vertical space.
        layout.setContentsMargins(
            16, 9, 16, 9
        )
        layout.setSpacing(4)

        self.step_label = QLabel()
        set_themed_stylesheet(
            self.step_label,
            """
            QLabel {
                background-color: #fff4df;
                border: 1px solid #d9bd82;
                border-radius: 9px;
                padding: 3px 8px;
                font-family: Georgia;
                font-size: 10px;
                font-weight: 800;
                color: #6c5428;
            }
            """,
        )
        self.step_label.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.step_label)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        set_themed_stylesheet(
            self.title_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 18px;
                font-weight: 900;
                color: #25190f;
                padding: 1px 0px;
            }
            """,
        )
        layout.addWidget(self.title_label)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        
        set_themed_stylesheet(
            self.text_label,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 600;
                color: #25190f;
                line-height: 1.2;
            }
            """,
        )
        layout.addWidget(self.text_label)

        self.action_hint = QLabel()
        self.action_hint.setWordWrap(True)
        set_themed_stylesheet(
            self.action_hint,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 800;
                color: #8a6726;
            }
            """,
        )
        layout.addWidget(self.action_hint)

        buttons = QHBoxLayout()

        self.skip_btn = QPushButton(
            "Skip Tutorial"
        )
        self.back_btn = QPushButton(
            "← Back"
        )
        self.next_btn = QPushButton(
            "Next →"
        )

        self.skip_btn.clicked.connect(
            self.controller.stop
        )
        self.back_btn.clicked.connect(
            self.controller.previous
        )
        self.next_btn.clicked.connect(
            self.controller.next
        )

        set_themed_stylesheet(
            self.skip_btn,
            """
            QPushButton {
                background: transparent;
                border: none;
                padding: 4px 5px;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 700;
                color: #806c4d;
                text-decoration: underline;
            }

            QPushButton:hover {
                background: transparent;
                border: none;
                color: #4f3b18;
            }
            """,
        )

        buttons.addWidget(self.skip_btn)
        buttons.addStretch()
        buttons.addWidget(self.back_btn)
        buttons.addWidget(self.next_btn)

        layout.addLayout(buttons)

        self.card.setFixedWidth(300)

    # ---------------------------------------------------------
    # Spotlight shape helpers
    # ---------------------------------------------------------

    def _widget_corner_radius(
        self,
        widget,
        fallback=12,
    ):
        """
        Try to use the real widget's QSS border-radius so the tutorial
        outline follows the same rounded corners as the control itself.
        """
        if widget is None:
            return fallback

        try:
            stylesheet = widget.styleSheet() or ""
        except Exception:
            stylesheet = ""

        import re

        match = re.search(
            r"border-radius\s*:\s*(\d+)px",
            stylesheet,
            flags=re.IGNORECASE,
        )

        if match is not None:
            try:
                return max(
                    0,
                    int(match.group(1)),
                )
            except (TypeError, ValueError):
                pass

        try:
            height = widget.height()
        except Exception:
            height = 0

        if height > 0:
            return min(
                fallback,
                max(
                    6,
                    height // 4,
                ),
            )

        return fallback

    def _rounded_region(
        self,
        rect,
        radius,
    ):
        path = QPainterPath()
        path.addRoundedRect(
            rect,
            radius,
            radius,
        )

        polygon = (
            path
            .toFillPolygon()
            .toPolygon()
        )

        return QRegion(
            polygon
        )

    # ---------------------------------------------------------
    # Geometry / presentation
    # ---------------------------------------------------------

    def _sync_border_layer_host(
        self,
        host,
    ):
        try:
            if self.border_layer.parentWidget() is not host:
                self.border_layer.hide()
                self.border_layer.setParent(
                    host
                )

            self.border_layer.setGeometry(
                0,
                0,
                host.width(),
                host.height(),
            )

        except (
            RuntimeError,
            ReferenceError,
        ):
            pass

    def _update_border_layer(self):
        try:
            if (
                not self.isVisible()
                or self.highlight_rect.isNull()
            ):
                self.border_layer.hide()
                return

            self.border_layer.setGeometry(
                0,
                0,
                self.active_host.width(),
                self.active_host.height(),
            )

            self.border_layer.set_spotlight(
                self.highlight_rect,
                self.highlight_radius,
                self.highlight_pen_width,
            )

        except (
            RuntimeError,
            ReferenceError,
        ):
            pass

    def hideEvent(self, event):
        try:
            self.border_layer.hide()
        except (
            RuntimeError,
            ReferenceError,
        ):
            pass

        super().hideEvent(event)

    def sync_to_host(self, host=None):
        if host is None:
            host = self.host

        self.active_host = host

        if self.parentWidget() is not host:
            self.setParent(host)
            
        self.setGeometry(
            0,
            0,
            host.width(),
            host.height(),
        )

        self._sync_border_layer_host(
            host
        )

        self.raise_()

    def restore_to_base_host(self):
        """
        Move the reusable tutorial UI back to the normal sheet before a
        temporary tutorial dialog is closed or deleted.

        Dialog steps temporarily parent the overlay to that dialog. If the
        dialog is deleted while the overlay is still its child, Qt deletes
        the overlay and TutorialCard too. The Python references then point
        to dead C++ objects, causing 'Internal C++ object already deleted'.
        """
        try:
            if self.card.parentWidget() is not self:
                self.card.hide()
                self.card.setWindowFlags(
                    Qt.WindowType.Widget
                )
                self.card.setParent(
                    self
                )

            self.border_layer.hide()

            self.clearMask()
            self.sync_to_host(
                self.host
            )
            self.hide()

        except (
            RuntimeError,
            ReferenceError,
        ):
            # If Qt is already tearing down a stale dialog wrapper,
            # there is nothing useful left to reparent.
            return

    def set_widget_step(
        self,
        step: TutorialStep,
        index: int,
        count: int,
    ):
        self.highlight_pen_width = 4

        card_layout = self.card.layout()

        self.card.setFixedWidth(300)

        if card_layout is not None:
            card_layout.setContentsMargins(
                16, 9, 16, 9
            )
            card_layout.setSpacing(4)

        self.step_label.show()
        self.title_label.show()
        self.text_label.show()
        self.action_hint.show()
        self.skip_btn.show()

        self.clearMask()
        self.sync_to_host(self.host)

        self.target_widget = step.target()

        if self.target_widget is None:
            self.highlight_rect = QRect()
            self.highlight_radius = 12

        else:
            top_left = self.target_widget.mapTo(
                self.active_host,
                QPoint(0, 0),
            )

            # The Name tutorial step should spotlight the complete
            # "Name + field" control as one unit, not only the text inside
            # the QLineEdit.  The caption and editor are separate widgets
            # in the real top bar, so build one rectangle around both.
            name_field = getattr(
                self.controller.host,
                "character_name_label",
                None,
            )
            name_caption = getattr(
                self.controller.host,
                "name_caption",
                None,
            )

            if (
                step.tight_to_text
                and self.target_widget is name_field
                and name_caption is not None
            ):
                caption_top_left = name_caption.mapTo(
                    self.active_host,
                    QPoint(0, 0),
                )

                field_top_left = name_field.mapTo(
                    self.active_host,
                    QPoint(0, 0),
                )

                caption_rect = QRect(
                    caption_top_left,
                    name_caption.size(),
                )

                field_rect = QRect(
                    field_top_left,
                    name_field.size(),
                )

                rect = caption_rect.united(
                    field_rect
                )

                # The Name caption and editor are separate widgets, so
                # this one tutorial target has no single existing outer box.
                # Give that combined control only a very small frame.
                rect.adjust(
                    -6,
                    -2,
                    6,
                    2,
                )

                # This is one artificial outline around two separate
                # widgets (the "Name" caption + the editable field).
                # A 10px radius is too tight once the tutorial outline is
                # 6px thick, which makes the corners look pinched.
                # Use the same soft rounding as the rest of the sheet.
                self.highlight_radius = min(
                    18,
                    max(
                        12,
                        rect.height() // 3,
                    ),
                )

            elif (
                step.tight_to_text
                and hasattr(
                    self.target_widget,
                    "text",
                )
            ):
                try:
                    text_value = self.target_widget.text()
                except TypeError:
                    text_value = ""

                if (
                    not text_value
                    and hasattr(
                        self.target_widget,
                        "placeholderText",
                    )
                ):
                    text_value = (
                        self.target_widget.placeholderText()
                    )

                metrics = self.target_widget.fontMetrics()

                text_width = max(
                    1,
                    metrics.horizontalAdvance(
                        str(text_value)
                    ),
                )

                text_height = max(
                    1,
                    metrics.height(),
                )

                rect_width = min(
                    self.target_widget.width(),
                    text_width + 28,
                )

                rect_height = min(
                    self.target_widget.height(),
                    text_height + 14,
                )

                x_offset = max(
                    0,
                    (
                        self.target_widget.width()
                        - rect_width
                    ) // 2,
                )

                y_offset = max(
                    0,
                    (
                        self.target_widget.height()
                        - rect_height
                    ) // 2,
                )

                rect = QRect(
                    top_left.x() + x_offset,
                    top_left.y() + y_offset,
                    rect_width,
                    rect_height,
                )

            else:
                rect = QRect(
                    top_left,
                    self.target_widget.size(),
                )

                host = self.controller.host

                # HeartsPanel reserves enough width for many future hearts.
                # Spotlight only the heart widgets that actually exist now.
                if (
                    self.target_widget
                    is getattr(
                        host,
                        "hp_panel",
                        None,
                    )
                ):
                    heart_widgets = getattr(
                        self.target_widget,
                        "heart_widgets",
                        [],
                    )

                    if heart_widgets:
                        heart_rect = QRect()
                        first_heart = True

                        for heart in heart_widgets:
                            heart_top_left = heart.mapTo(
                                self.active_host,
                                QPoint(0, 0),
                            )

                            current_rect = QRect(
                                heart_top_left,
                                heart.size(),
                            )

                            if first_heart:
                                heart_rect = QRect(
                                    current_rect
                                )
                                first_heart = False
                            else:
                                heart_rect = (
                                    heart_rect.united(
                                        current_rect
                                    )
                                )

                        heart_rect.adjust(
                            -7,
                            -5,
                            7,
                            5,
                        )

                        rect = heart_rect
                        self.highlight_radius = 12

                # ATWidget expands horizontally even when only a few
                # diamonds exist. Spotlight the actual drawn diamonds.
                elif (
                    self.target_widget
                    is getattr(
                        host,
                        "at_box",
                        None,
                    )
                ):
                    count_at = int(
                        getattr(
                            host.character.adversity,
                            "max_AT",
                            0,
                        )
                    )

                    if count_at > 0:
                        at_layout = (
                            self.target_widget
                            .calculate_layout(
                                count_at
                            )
                        )

                        per_row = int(
                            at_layout.get(
                                "per_row",
                                0,
                            )
                        )
                        diamond_size = float(
                            at_layout.get(
                                "diamond_size",
                                0,
                            )
                        )

                        if (
                            per_row > 0
                            and diamond_size > 0
                        ):
                            rows = (
                                count_at
                                + per_row
                                - 1
                            ) // per_row

                            widest_count = min(
                                count_at,
                                per_row,
                            )

                            h_gap = float(
                                at_layout.get(
                                    "h_gap",
                                    0,
                                )
                            )
                            v_gap = float(
                                at_layout.get(
                                    "v_gap",
                                    0,
                                )
                            )

                            local_x = float(
                                at_layout.get(
                                    "start_x",
                                    0,
                                )
                            )
                            local_y = float(
                                at_layout.get(
                                    "start_y",
                                    0,
                                )
                            )

                            content_width = (
                                widest_count
                                * diamond_size
                                + max(
                                    0,
                                    widest_count - 1,
                                )
                                * h_gap
                            )

                            content_height = (
                                rows
                                * diamond_size
                                + max(
                                    0,
                                    rows - 1,
                                )
                                * v_gap
                            )

                            at_top_left = (
                                self.target_widget
                                .mapTo(
                                    self.active_host,
                                    QPoint(
                                        int(local_x),
                                        int(local_y),
                                    ),
                                )
                            )

                            rect = QRect(
                                at_top_left.x() - 7,
                                at_top_left.y() - 7,
                                int(content_width) + 14,
                                int(content_height) + 14,
                            )

                            self.highlight_radius = 12

            if not (
                step.tight_to_text
                and self.target_widget is name_field
                and name_caption is not None
                or self.target_widget
                in {
                    getattr(
                        self.controller.host,
                        "hp_panel",
                        None,
                    ),
                    getattr(
                        self.controller.host,
                        "at_box",
                        None,
                    ),
                }
            ):
                self.highlight_radius = (
                    self._widget_corner_radius(
                        self.target_widget,
                        fallback=12,
                    )
                )

            # Optional extra room around a particular tutorial target.
            # This enlarges the BLACK spotlight box without changing the
            # tutorial explanation card itself.
            spotlight_padding = max(
                0,
                int(step.padding),
            )

            if spotlight_padding:
                rect.adjust(
                    -spotlight_padding,
                    -spotlight_padding,
                    spotlight_padding,
                    spotlight_padding,
                )

                # Grow the corner radius by the same amount so rounded/pill
                # controls keep the same smooth shape at the larger size.
                self.highlight_radius += spotlight_padding

            self.highlight_rect = (
                rect.intersected(
                    self.rect()
                )
            )

        self._set_text(
            step.title,
            step.text,
            index,
            count,
        )

        self.next_btn.setVisible(
            not step.require_action
        )

        if step.advance_on_click:
            self.action_hint.setText(
                "Click the highlighted control to continue."
            )
        else:
            self.action_hint.setText("")

        self._resize_card_to_content()

        self.show()
        self.raise_()
        self._update_border_layer()

        self.card.show()
        self.card.raise_()
        
        self.position_card()

        self.update_interaction_mask(
            step.allow_interaction
        )
        self.update()

    def set_menu_step(
        self,
        step: TutorialMenuStep,
        index: int,
        count: int,
    ):
        self.card.setFixedWidth(300)
        self.step_label.show()
        self.title_label.show()
        self.text_label.show()
        self.action_hint.show()
        self.skip_btn.show()

        self.clearMask()
        self.sync_to_host(self.host)

        self.target_widget = getattr(
            self.host,
            "tools_toggle_btn",
            None,
        )

        if self.target_widget is not None:
            top_left = self.target_widget.mapTo(
                self.active_host,
                QPoint(0, 0),
            )

            rect = QRect(
                top_left,
                self.target_widget.size(),
            )

            self.highlight_radius = 12

            self.highlight_rect = (
                rect.intersected(
                    self.rect()
                )
            )
        else:
            self.highlight_rect = QRect()

        self._set_text(
            step.title,
            step.text,
            index,
            count,
        )

        self.next_btn.setVisible(
            not step.require_action
        )

        if step.require_action:
            self.action_hint.setText(
                f"Choose {step.action_text} from the highlighted menu."
            )
        else:
            self.action_hint.setText(
                "This command is inside Tools."
            )

        self._resize_card_to_content()

        self.show()
        self.raise_()
        self._update_border_layer()

        self.card.show()
        self.card.raise_()
        
        self.position_card()
        self.update()

    def _set_text(
        self,
        title: str,
        text: str,
        index: int,
        count: int,
    ):
        self.step_label.setText(
            f"Step {index + 1} of {count}"
        )
        self.title_label.setText(title)
        self.text_label.setText(text)

        self.back_btn.setVisible(
            index > 0
        )

        self.next_btn.setText(
            "Finish"
            if index == count - 1
            else "Next →"
        )

        # Card height is calculated after each step has finished setting
        # its action hint / button visibility.  Doing it here was too early
        # for menu steps, where the hint is assigned immediately after
        # _set_text().  On some Windows DPI/font combinations that left the
        # card one wrapped line too short and clipped the beginning/end of
        # the instructions.

    def _resize_card_to_content(self):
        """
        Size the tutorial card from the real rendered font.

        Do not use QFontMetrics.boundingRect() for wrapped Georgia text here.
        On Windows it can under-report the first layout pass and clip the top
        or bottom of a line until another window event causes a relayout.

        QTextDocument uses Qt's actual text-layout engine, so the first size
        and later sizes stay identical.
        """
        layout = self.card.layout()

        if layout is None:
            return

        self.card.ensurePolished()

        self.action_hint.setVisible(
            bool(
                str(
                    self.action_hint.text()
                    or ""
                ).strip()
            )
        )

        self.card.setMinimumHeight(0)
        self.card.setMaximumHeight(16777215)

        margins = layout.contentsMargins()

        content_width = max(
            1,
            self.card.width()
            - margins.left()
            - margins.right(),
        )

        for label in (
            self.title_label,
            self.text_label,
            self.action_hint,
        ):
            label.setMinimumHeight(0)
            label.setMaximumHeight(16777215)

            # Do NOT use isVisible() here. _resize_card_to_content() is
            # intentionally called before the tutorial card/overlay itself
            # is shown. In Qt, isVisible() is False whenever an ancestor is
            # hidden, even when this label has explicitly been shown for the
            # current step. That made the first sizing pass skip the title
            # and body entirely; a later relayout then changed the card
            # height after switching windows or calling the sizing method
            # again.
            #
            # isHidden() checks whether THIS label was explicitly hidden,
            # which is exactly what we need for optional rows such as the
            # action hint while still measuring title/body before first show.
            if label.isHidden():
                continue

            label.ensurePolished()

            # Let the layout own the width. Only calculate the height.
            label.setMinimumWidth(0)
            label.setMaximumWidth(16777215)

            document = QTextDocument()
            document.setDocumentMargin(0)
            document.setDefaultFont(
                label.font()
            )
            document.setPlainText(
                str(
                    label.text()
                    or ""
                )
            )
            document.setTextWidth(
                float(content_width)
            )

            required_height = math.ceil(
                document.documentLayout()
                .documentSize()
                .height()
            )

            # QTextDocument and QLabel can differ slightly in wrapped
            # Georgia text metrics on Windows. The tutorial body needs a
            # little more room than a single glyph-edge allowance, otherwise
            # the final wrapped line can be clipped (for example Level Up).
            safety_height = (
                10
                if label is self.text_label
                else 6
            )

            label.setFixedHeight(
                required_height
                + safety_height
            )

        layout.invalidate()
        layout.activate()

        self.card.setFixedHeight(
            layout.sizeHint().height() + 4
        )

    def position_card(self):
        margin = 16
        card_w = self.card.width()
        card_h = self.card.height()

        target = self.highlight_rect

        if target.isNull():
            self.card.move(
                max(
                    margin,
                    (self.width() - card_w) // 2,
                ),
                max(
                    margin,
                    (self.height() - card_h) // 2,
                ),
            )
            return

        candidates = [
            (
                target.right() + margin,
                target.top(),
            ),
            (
                target.left()
                - card_w
                - margin,
                target.top(),
            ),
            (
                target.left(),
                target.bottom() + margin,
            ),
            (
                target.left(),
                target.top()
                - card_h
                - margin,
            ),
        ]

        for x, y in candidates:
            if (
                x >= margin
                and y >= margin
                and x + card_w
                <= self.width() - margin
                and y + card_h
                <= self.height() - margin
            ):
                self.card.move(x, y)
                return
            
        # Fallback: choose the side with the most free space.
        space_left = target.left()
        space_right = self.width() - target.right()
        space_above = target.top()
        space_below = self.height() - target.bottom()

        spaces = {
            "left": space_left,
            "right": space_right,
            "above": space_above,
            "below": space_below,
        }

        best_side = max(
            spaces,
            key=spaces.get,
        )

        if best_side == "left":
            x = target.left() - card_w - margin
            y = target.center().y() - card_h // 2

        elif best_side == "right":
            x = target.right() + margin
            y = target.center().y() - card_h // 2

        elif best_side == "above":
            x = target.center().x() - card_w // 2
            y = target.top() - card_h - margin

        else:
            x = target.center().x() - card_w // 2
            y = target.bottom() + margin

        x = max(
            margin,
            min(
                x,
                self.width() - card_w - margin,
            ),
        )

        y = max(
            margin,
            min(
                y,
                self.height() - card_h - margin,
            ),
        )

        self.card.move(
            x,
            y,
        )

    # ---------------------------------------------------------
    # Painting
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        full = QPainterPath()
        full.addRect(self.rect())

        if self.highlight_rect.isNull():
            shade = full
        else:
            hole = QPainterPath()
            hole.addRoundedRect(
                self.highlight_rect,
                self.highlight_radius,
                self.highlight_radius,
            )
            shade = full.subtracted(hole)

        painter.fillPath(
            shade,
            QColor(
                38,
                28,
                18,
                118,
            ),
        )

        # Do NOT paint the black ring here. Interactive tutorial steps
        # mask this widget around the target, which clips a centered stroke.
        # SpotlightBorderLayer paints the complete ring above this overlay.

    # ---------------------------------------------------------
    # Optional real-control clicks
    # ---------------------------------------------------------

    def mousePressEvent(self, event):
        step = self.controller.current_step()

        if not isinstance(
            step,
            TutorialStep,
        ):
            super().mousePressEvent(event)
            return

        if (
            step.advance_on_click
            and self.target_widget is not None
            and self.highlight_rect.contains(
                event.position().toPoint()
            )
        ):
            self._forward_click(
                event,
                self.target_widget,
            )
            return

        super().mousePressEvent(event)

    def _forward_click(
        self,
        source_event: QMouseEvent,
        target: QWidget,
    ):
        global_pos = (
            source_event.globalPosition()
        )

        local_pos = target.mapFromGlobal(
            global_pos.toPoint()
        )

        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local_pos,
            global_pos,
            source_event.button(),
            source_event.buttons(),
            source_event.modifiers(),
        )

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            local_pos,
            global_pos,
            source_event.button(),
            Qt.MouseButton.NoButton,
            source_event.modifiers(),
        )

        QApplication.sendEvent(
            target,
            press,
        )

        QApplication.sendEvent(
            target,
            release,
        )

        QTimer.singleShot(
            80,
            self.controller.complete_current_step,
        )


    def _float_card_beside_dialog(self, dialog):
        self.card.setParent(
            dialog
        )

        self.card.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.card.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.card.setFixedWidth(300)

        self.card.layout().activate()
        self.card.adjustSize()

        dialog_rect = dialog.frameGeometry()

        screen = QApplication.screenAt(
            dialog.mapToGlobal(
                dialog.rect().center()
            )
        )

        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is None:
            return

        available = screen.availableGeometry()

        gap = 16
        edge = 8

        combined_width = (
            dialog_rect.width()
            + gap
            + self.card.width()
        )

        if (
            combined_width
            <= available.width()
            - (edge * 2)
        ):
            dialog.move(
                available.left() + edge,
                dialog_rect.top(),
            )

            dialog_rect = dialog.frameGeometry()

            card_x = (
                dialog_rect.right()
                + gap
            )

        else:
            card_x = max(
                available.left() + edge,
                dialog_rect.left()
                - self.card.width()
                - gap,
            )

        card_y = max(
            available.top() + edge,
            min(
                dialog_rect.center().y()
                - self.card.height() // 2,
                available.bottom()
                - self.card.height()
                - edge,
            ),
        )

        self.card.move(
            card_x,
            card_y,
        )

        self.card.show()
        self.card.raise_()

    def move_card_outside_dialog(
        self,
        dialog,
    ):
        self.card.hide()
        self.card.setParent(
            dialog
        )

        self.card.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.card.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.card.setFixedWidth(320)

        self.card.layout().activate()
        self.card.adjustSize()

        screen = QApplication.screenAt(
            dialog.mapToGlobal(
                dialog.rect().center()
            )
        )

        if screen is None:
            screen = QApplication.primaryScreen()

        available = screen.availableGeometry()

        gap = 16

        dialog_rect = dialog.frameGeometry()

        card_width = self.card.width()
        card_height = self.card.height()

        # ---------------------------------------------------------
        # First try placing the tutorial card on the RIGHT.
        # ---------------------------------------------------------

        right_x = (
            dialog_rect.right()
            + gap
        )

        if (
            right_x + card_width
            <= available.right()
        ):
            x = right_x

        else:
            # -----------------------------------------------------
            # Then try the LEFT.
            # -----------------------------------------------------

            left_x = (
                dialog_rect.left()
                - card_width
                - gap
            )

            if left_x >= available.left():
                x = left_x

            else:
                # -------------------------------------------------
                # There is not enough room on either side.
                # Move the dialog LEFT to create room on the right.
                # -------------------------------------------------

                needed_right_edge = (
                    available.right()
                    - card_width
                    - gap
                )

                shift_left = max(
                    0,
                    dialog_rect.right()
                    - needed_right_edge,
                )

                new_dialog_x = max(
                    available.left() + gap,
                    dialog.x() - shift_left,
                )

                dialog.move(
                    new_dialog_x,
                    dialog.y(),
                )

                dialog_rect = (
                    dialog.frameGeometry()
                )

                x = (
                    dialog_rect.right()
                    + gap
                )

        # Keep the tutorial card vertically aligned
        # with the top of the dialog.
        y = max(
            available.top() + gap,
            min(
                dialog_rect.top(),
                available.bottom()
                - card_height
                - gap,
            ),
        )

        self.card.move(
            x,
            y,
        )

        self.card.show()
        self.card.raise_()

        dialog.raise_()
        dialog.activateWindow()

        self.card.raise_()

    def set_dialog_step(
        self,
        step,
        dialog,
        target,
        index,
        count,
    ):
        self.highlight_pen_width = 4
        if self.card.parentWidget() is not self:
            self.card.hide()
            self.card.setWindowFlags(
                Qt.WindowType.Widget
            )
            self.card.setParent(
                self
            )
            self.card.show()

        self.card.setFixedWidth(300)
        self.step_label.show()
        self.title_label.show()
        self.text_label.show()
        self.action_hint.show()
        self.skip_btn.show()

        self.clearMask()
        self.sync_to_host(dialog)

        self.target_widget = target

        if target is None:
            self.highlight_rect = QRect()
            self.highlight_radius = 12
        else:
            top_left = target.mapTo(
                dialog,
                QPoint(0, 0),
            )

            rect = QRect(
                top_left,
                target.size(),
            )

            self.highlight_radius = (
                self._widget_corner_radius(
                    target,
                    fallback=12,
                )
            )

            # Exact fit: no tutorial padding around the existing control.
            self.highlight_rect = (
                rect.intersected(
                    self.rect()
                )
            )

        self._set_text(
            step.title,
            step.text,
            index,
            count,
        )

        if step.require_action:
            self.back_btn.hide()

        self.next_btn.setVisible(
            not step.require_action
        )
        self.action_hint.setText("")

        self._resize_card_to_content()

        if step.float_card_outside:
            self.show()
            self.raise_()
            self._update_border_layer()

            if step.interaction_mode == "target":
                full_region = QRegion(
                    self.rect()
                )

                hole_region = (
                    self._rounded_region(
                        self.highlight_rect,
                        self.highlight_radius,
                    )
                )

                self.setMask(
                    full_region.subtracted(
                        hole_region
                    )
                )

            else:
                self.clearMask()

            self._float_card_beside_dialog(dialog)

            dialog.raise_()
            dialog.activateWindow()
            self.card.raise_()
            self.update()
            return

        # ---------------------------------------------------------
        # Full-dialog interaction step:
        # The player must be able to click every ability card.
        # Show only a compact help banner in the otherwise-unused
        # upper-left header area instead of covering the grid.
        # ---------------------------------------------------------
        if step.interaction_mode == "all":
            self.clearMask()
            self.hide()

            # -----------------------------------------------------
            # The player needs the ENTIRE Edit Abilities dialog.
            # Make the tutorial card a separate floating tool window
            # and place it OUTSIDE the dialog instead of over it.
            # -----------------------------------------------------

            self.card.setParent(
                dialog
            )

            self.card.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )

            self.card.setAttribute(
                Qt.WidgetAttribute.WA_ShowWithoutActivating,
                True,
            )

            self.card.setFixedWidth(
                330
            )

            # Keep the teaching card visible while leaving the whole grid
            # interactive. The player may try changing dice, but no action is
            # required, so Back and Next must always remain available.
            self.step_label.show()
            self.title_label.show()
            self.text_label.show()
            self.action_hint.hide()
            self.back_btn.show()
            self.next_btn.show()
            self.skip_btn.show()

            self._resize_card_to_content()

            dialog_rect = dialog.frameGeometry()

            dialog_center_global = dialog.mapToGlobal(
                dialog.rect().center()
            )

            screen = QApplication.screenAt(
                dialog_center_global
            )

            if screen is None:
                screen = QApplication.primaryScreen()

            if screen is not None:
                available = screen.availableGeometry()
            else:
                available = dialog_rect.adjusted(
                    -500,
                    -500,
                    500,
                    500,
                )

            gap = 18

            card_w = self.card.width()
            card_h = self.card.height()

            # Prefer the right side.
            right_x = (
                dialog_rect.right()
                + gap
            )

            left_x = (
                dialog_rect.left()
                - card_w
                - gap
            )

            centered_y = (
                dialog_rect.center().y()
                - card_h // 2
            )

            centered_y = max(
                available.top() + gap,
                min(
                    centered_y,
                    available.bottom()
                    - card_h
                    - gap,
                ),
            )

            if (
                right_x + card_w
                <= available.right() - gap
            ):
                card_x = right_x
                card_y = centered_y

            elif (
                left_x
                >= available.left() + gap
            ):
                card_x = left_x
                card_y = centered_y

            else:
                # If the dialog currently uses almost the full screen,
                # create room beside it by moving it slightly rather than
                # covering the ability cards.
                needed_width = (
                    card_w
                    + gap
                )

                room_on_right = (
                    available.right()
                    - dialog_rect.right()
                )

                room_on_left = (
                    dialog_rect.left()
                    - available.left()
                )

                if room_on_right >= room_on_left:
                    shift = max(
                        0,
                        needed_width
                        - room_on_right
                        + gap,
                    )

                    new_dialog_x = max(
                        available.left() + gap,
                        dialog.x() - shift,
                    )

                    dialog.move(
                        new_dialog_x,
                        dialog.y(),
                    )

                    dialog_rect = (
                        dialog.frameGeometry()
                    )

                    card_x = (
                        dialog_rect.right()
                        + gap
                    )

                else:
                    shift = max(
                        0,
                        needed_width
                        - room_on_left
                        + gap,
                    )

                    new_dialog_x = min(
                        available.right()
                        - dialog.width()
                        - gap,
                        dialog.x() + shift,
                    )

                    dialog.move(
                        new_dialog_x,
                        dialog.y(),
                    )

                    dialog_rect = (
                        dialog.frameGeometry()
                    )

                    card_x = (
                        dialog_rect.left()
                        - card_w
                        - gap
                    )

                card_y = max(
                    available.top() + gap,
                    min(
                        dialog_rect.center().y()
                        - card_h // 2,
                        available.bottom()
                        - card_h
                        - gap,
                    ),
                )

            self.card.move(
                card_x,
                card_y,
            )

            self.card.show()
            self.card.raise_()

            # -----------------------------------------------------
            # Keep a spotlight around the ENTIRE six-ability grid.
            #
            # FantasyAbilityEditorDialog gives each ability card the
            # object name "StatCell" or "StatCellSelected". Build one
            # rectangle around all six cards, leave that area clickable,
            # and dim everything else in the Edit Abilities dialog.
            # -----------------------------------------------------

            stat_cells = [
                child
                for child in dialog.findChildren(QFrame)
                if child.objectName()
                in {
                    "StatCell",
                    "StatCellSelected",
                }
            ]

            if stat_cells:
                grid_rect = QRect()
                first_cell = True

                for cell in stat_cells:
                    cell_top_left = cell.mapTo(
                        dialog,
                        QPoint(0, 0),
                    )

                    cell_rect = QRect(
                        cell_top_left,
                        cell.size(),
                    )

                    if first_cell:
                        grid_rect = QRect(
                            cell_rect
                        )
                        first_cell = False
                    else:
                        grid_rect = grid_rect.united(
                            cell_rect
                        )

                # Small breathing room around the full grid.
                grid_rect.adjust(
                    -8,
                    -8,
                    8,
                    8,
                )

                self.highlight_rect = (
                    grid_rect.intersected(
                        self.rect()
                    )
                )

                self.highlight_radius = 12

                full_region = QRegion(
                    self.rect()
                )

                hole_region = (
                    self._rounded_region(
                        self.highlight_rect,
                        self.highlight_radius,
                    )
                )

                self.setMask(
                    full_region.subtracted(
                        hole_region
                    )
                )

                # Re-show the overlay so it paints the dimming and bold
                # black outline while the rounded hole stays clickable.
                self.show()
                self.raise_()
                self._update_border_layer()
                self.update()

            dialog.raise_()
            dialog.activateWindow()

            # The help card is a separate top-level tool window.
            self.card.raise_()

            return

        self.show()
        self.raise_()
        self._update_border_layer()
        self.card.raise_()

        self.position_card()

        if step.interaction_mode == "target":
            full_region = QRegion(
                self.rect()
            )

            hole_region = (
                self._rounded_region(
                    self.highlight_rect,
                    self.highlight_radius,
                )
            )

            self.setMask(
                full_region.subtracted(
                    hole_region
                )
            )

        else:
            self.clearMask()

        if step.card_outside_dialog:
            self.move_card_outside_dialog(dialog)

        else:
            self.card.show()
            self.card.raise_()
            self.position_card()

        self.update()

    def update_interaction_mask(
        self,
        allow_interaction=False,
    ):
        if (
            not allow_interaction
            or self.highlight_rect.isNull()
        ):
            self.clearMask()
            return

        full_region = QRegion(
            self.rect()
        )

        hole_region = (
            self._rounded_region(
                self.highlight_rect,
                self.highlight_radius,
            )
        )

        # Remove only the highlighted control from the overlay.
        # Mouse input can pass through there.
        region = full_region.subtracted(
            hole_region
        )

        self.setMask(
            region
        )

        # The card must remain a normal interactive child.
        self.card.raise_()

class GuidedTutorial(QObject):
    def __init__(
        self,
        host: QWidget,
        steps: list[TutorialAnyStep],
        parent: Optional[QObject] = None,
    ):
        super().__init__(
            parent or host
        )

        self.host = host
        self.steps = list(steps)
        self._enter_advance_target = None
        self._prepared_index = None

        self.index = -1
        self.running = False

        self.completion_timer = QTimer(self)
        self.completion_timer.setInterval(150)
        self.completion_timer.timeout.connect(
            self.check_completion
        )

        # The sheet itself lives in the QMainWindow's central widget.
        # Putting the overlay there keeps its geometry aligned with the
        # visible character sheet instead of including the window frame.
        self.overlay_host = (
            host.centralWidget()
            if (
                hasattr(host, "centralWidget")
                and host.centralWidget() is not None
            )
            else host
        )

        self.overlay = SpotlightOverlay(
            self.overlay_host,
            self,
        )

        self.tutorial_tools_menu: Optional[
            QMenu
        ] = None

        self._allow_tutorial_menu_close = False
        self._tutorial_app_inactive = False

        # Tutorial-only Tool windows must disappear when the user switches
        # to another application. Without this, a top-level QMenu can remain
        # visible over Chrome/Explorer on Windows.
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(
                self._on_application_state_changed
            )

        self.overlay_host.installEventFilter(
            self
        )

    def start(self):
        if not self.steps:
            return

        self.running = True
        self.completion_timer.start()
        self.index = 0
        self._prepared_index = None
        self.show_current()

    def stop(self):
        step = self.current_step()

        after_complete = getattr(
            step,
            "after_complete",
            None,
        )

        if after_complete is not None:
            try:
                after_complete()
            except Exception:
                pass

        # A skipped Inventory step may still have temporarily replaced the
        # real + button callback. Always restore it before leaving tutorial
        # mode, even if the demonstration dialog was never opened.
        if hasattr(
            self.host,
            "restore_inventory_add_button_after_tutorial",
        ):
            try:
                self.host.restore_inventory_add_button_after_tutorial()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

        self._clear_enter_advance()
        self._close_tutorial_menu()

        self.running = False
        self.completion_timer.stop()
        self.index = -1
        self._prepared_index = None

        # A dialog may still own the overlay when Skip Tutorial is used.
        # Rehome it before the frontend closes/deletes that dialog.
        self.overlay.restore_to_base_host()

        if hasattr(
            self.host,
            "close_tutorial_dialog",
        ):
            try:
                self.host.close_tutorial_dialog()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

        if (
            hasattr(
                self.host,
                "_tutorial_notes_were_visible",
            )
            and hasattr(
                self.host,
                "restore_notes_after_tutorial",
            )
        ):
            try:
                self.host.restore_notes_after_tutorial()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

    def current_step(
        self,
    ) -> Optional[TutorialAnyStep]:

        if (
            self.running
            and 0 <= self.index < len(self.steps)
        ):
            return self.steps[
                self.index
            ]

        return None

    def _run_before_show_once(
        self,
        step,
    ):
        """Run stateful step setup once per actual step entry.

        show_current() is also used to repaint after resize/move events and to
        reopen a tutorial menu. Re-running before_show during those repaints
        can reset completion baselines (Inventory/Notes) and make a finished
        action look unfinished again.
        """
        if self._prepared_index == self.index:
            return

        before_show = getattr(
            step,
            "before_show",
            None,
        )

        if before_show is not None:
            before_show()

        self._prepared_index = self.index

    def show_current(self):
        step = self.current_step()

        if step is None:
            self.stop()
            return

        self._close_tutorial_menu()

        if isinstance(
            step,
            TutorialMenuStep,
        ):
            self._run_before_show_once(
                step
            )

            self._show_menu_step(
                step
            )
            return

        if isinstance(
            step,
            TutorialDialogStep,
        ):
            self._show_dialog_step(step)
            return

        self._run_before_show_once(
            step
        )

        def show_widget_step_safely():
            if not self.running:
                return

            # Back/Next can be pressed before an older zero-delay callback
            # has executed. Never allow a callback for an old step to repaint
            # the spotlight over the new current step.
            if self.current_step() is not step:
                return

            try:
                self.overlay.set_widget_step(
                    step,
                    self.index,
                    len(self.steps),
                )
            except (
                RuntimeError,
                ReferenceError,
            ) as error:
                message = str(
                    error
                ).lower()

                if (
                    "already deleted" in message
                    or "internal c++ object" in message
                    or "wrapped c/c++ object" in message
                ):
                    return

                raise

        QTimer.singleShot(
            0,
            show_widget_step_safely,
        )

    def next(self):
        step = self.current_step()

        # Dialog steps temporarily attach the reusable overlay to the
        # dialog. Detach it BEFORE any completion callback is allowed to
        # close/delete that dialog.
        if isinstance(
            step,
            TutorialDialogStep,
        ):
            self.overlay.restore_to_base_host()

        after_complete = getattr(
            step,
            "after_complete",
            None,
        )

        if after_complete is not None:
            try:
                after_complete()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

        self._close_tutorial_menu()

        if (
            self.index
            >= len(self.steps) - 1
        ):
            self.stop()
            return

        old_index = self.index
        new_index = self.index + 1

        # If a dialog step is moving directly into another dialog group
        # without an explicit cleanup callback, close the old demo first.
        if (
            isinstance(
                self.steps[old_index],
                TutorialDialogStep,
            )
            and not self._same_dialog_group(
                old_index,
                new_index,
            )
        ):
            self._close_current_tutorial_dialog_safely()

        self.index = new_index
        self._prepared_index = None
        self.show_current()

    def previous(self):
        if (
            not self.running
            or self.index <= 0
        ):
            return

        self._close_tutorial_menu()

        old_index = self.index
        new_index = self.index - 1

        old_step = self.steps[
            old_index
        ]

        # If Back is leaving one temporary-dialog group for a normal sheet
        # step or for a different dialog group, close that old dialog first.
        # If both steps belong to the same group, keep it open.
        if isinstance(
            old_step,
            TutorialDialogStep,
        ):
            if not self._same_dialog_group(
                old_index,
                new_index,
            ):
                self._close_current_tutorial_dialog_safely()

        self.index = new_index
        self._prepared_index = None
        self.show_current()

    def complete_current_step(self):
        self.next()

    # ---------------------------------------------------------
    # Tools menu teaching
    # ---------------------------------------------------------

    def _build_tutorial_tools_menu(
        self,
    ) -> QMenu:

        window = self.host
        menu = QMenu(window)

        dark_mode = (
            ui_theme_module.CURRENT_THEME
            == "dark"
        )

        menu_background = (
            "#182734"
            if dark_mode
            else "#fffdf7"
        )

        menu_text = (
            "#f5eee3"
            if dark_mode
            else "#25190f"
        )

        highlight_outline = (
            "#ffffff"
            if dark_mode
            else "#000000"
        )

        separator_color = (
            "#9a7b3f"
            if dark_mode
            else "#d9bd82"
        )

        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {menu_background};
                border: 1px solid #cdaa63;
                border-radius: 9px;
                padding: 5px;
                font-family: Georgia;
                font-size: 13px;
                font-weight: 700;
                color: {menu_text};
            }}

            QMenu::item {{
                padding: 5px 26px 5px 9px;
                margin: 1px 2px;
                border: 4px solid transparent;
                border-radius: 8px;
                background-color: transparent;
                color: {menu_text};
            }}

            QMenu::item:selected {{
                background-color: {menu_background};
                border: 4px solid {highlight_outline};
                border-radius: 8px;
                color: {menu_text};
            }}

            QMenu::item:disabled {{
                background-color: transparent;
                border: 4px solid transparent;
                color: {menu_text};
            }}

            QMenu::separator {{
                height: 1px;
                background-color: {separator_color};
                margin: 5px 7px;
            }}
            """
        )

        # Match the actual frontend's current Tools order.
        labels = [
            "New Character",
            "Save Character",
            "Load Character",
            "Delete Character",
            "Earlier Versions",
            "Edit Abilities",
        ]

        if getattr(
            window,
            "_available_update_release",
            None,
        ):
            labels.append(
                "Update Available"
            )

        labels.extend(
            [
                "How to Use",
                "Level Up",
                "Add Species",
            ]
        )

        for label in labels:
            action = menu.addAction(
                label
            )
            action.setEnabled(True)

        # Mirror the real fly-out for teaching purposes. This tutorial menu
        # is intentionally inert: it never rolls dice or changes settings.
        dice_menu = menu.addMenu("Dice Roller")
        dice_menu.addAction("Enabled")
        dice_menu.addAction("Roll Other Dice...")
        dice_menu.addAction("Previous Rolls (This Session)")

        menu.addSeparator()

        for label in (
            "Adjust Resources",
            "Improvement Editor",
        ):
            action = menu.addAction(
                label
            )
            action.setEnabled(True)

        creation_rules_menu = (
            menu.addMenu(
                "Creation Rules"
            )
        )

        creation_rules_menu.addAction(
            "Create Template"
        )

        creation_rules_menu.addAction(
            "New Character From Template"
        )

        return menu

    def _show_menu_step(
        self,
        step: TutorialMenuStep,
    ):
        self.overlay.set_menu_step(
            step,
            self.index,
            len(self.steps),
        )

        menu = (
            self._build_tutorial_tools_menu()
        )

        self.tutorial_tools_menu = menu

        action = next(
            (
                action
                for action in menu.actions()
                if action.text()
                == step.action_text
            ),
            None,
        )

        if action is not None:
            menu.setActiveAction(
                action
            )

            # During EVERY Tools tutorial step, only the command currently
            # being taught is selectable/highlightable. This prevents the
            # mouse from moving the bold tutorial outline onto unrelated
            # commands while the wizard is explaining a different one.
            for possible_action in menu.actions():
                possible_action.setEnabled(
                    possible_action is action
                )

            # During the Dice Roller tour, its three submenu choices are
            # visible for exploration, but are inert tutorial-only actions.
            # The normal Tools menu remains untouched.

            taught_callbacks = {
                "Load Character": getattr(
                    self.host,
                    "load_character_from_ui",
                    None,
                ),
                "Earlier Versions": getattr(
                    self.host,
                    "restore_previous_version_from_ui",
                    None,
                ),
                "Adjust Resources": getattr(
                    self.host,
                    "adjust_resources_from_ui",
                    None,
                ),
                "Update Available": getattr(
                    self.host,
                    "check_for_updates_from_ui",
                    None,
                ),
                "Add Species": getattr(
                    self.host,
                    "add_species_from_ui",
                    None,
                ),
                "Level Up": getattr(
                    self.host,
                    "level_up_from_ui",
                    None,
                ),
                "Save Character": getattr(
                    self.host,
                    "save_character_from_ui",
                    None,
                ),
            }

            taught_callback = taught_callbacks.get(
                step.action_text
            )

            if taught_callback is not None:
                def run_taught_action(
                    checked=False,
                    callback=taught_callback,
                    expected_step=step,
                ):
                    # Close the tutorial-only popup deliberately before the
                    # real action opens any dialog. This prevents the popup
                    # from reopening behind Species / Level Up / Save UI.
                    self._close_tutorial_menu()

                    callback()

                    if (
                        not self.running
                        or self.current_step()
                        is not expected_step
                    ):
                        return

                    check = getattr(
                        expected_step,
                        "completion_check",
                        None,
                    )

                    if check is not None:
                        try:
                            completed = bool(check())
                        except Exception:
                            completed = False

                        if completed:
                            QTimer.singleShot(
                                0,
                                self.next,
                            )
                        else:
                            # For example, Species selection was cancelled.
                            # Keep the player on the same tutorial step and
                            # reopen its teaching menu cleanly.
                            QTimer.singleShot(
                                0,
                                self.show_current,
                            )
                        return

                    QTimer.singleShot(
                        0,
                        self.next,
                    )

                action.triggered.connect(
                    run_taught_action
                )

        tools_button = getattr(
            self.host,
            "tools_toggle_btn",
            None,
        )

        if tools_button is None:
            return

        # This menu only needs to float above the DID window. Do NOT use
        # WindowStaysOnTopHint here: on Windows that can leave the tutorial
        # menu visibly floating over completely different applications.
        menu.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
        )

        def place_menu_on_screen():
            """Place the tutorial Tools menu fully inside the active screen."""
            menu.adjustSize()

            button_bottom = tools_button.mapToGlobal(
                tools_button.rect().bottomLeft()
            )
            button_top = tools_button.mapToGlobal(
                tools_button.rect().topLeft()
            )

            screen = QApplication.screenAt(button_bottom)
            if screen is None:
                screen = QApplication.primaryScreen()

            available = screen.availableGeometry()
            menu_size = menu.sizeHint()

            menu_x = button_bottom.x()
            menu_y = button_bottom.y()

            # Keep the entire menu on screen horizontally.
            menu_x = min(
                max(menu_x, available.left() + 8),
                max(
                    available.left() + 8,
                    available.right() - menu_size.width() - 8,
                ),
            )

            # Prefer below Tools. If it does not fit, open above it.
            if menu_y + menu_size.height() > available.bottom() - 8:
                menu_y = button_top.y() - menu_size.height()

            menu_y = min(
                max(menu_y, available.top() + 8),
                max(
                    available.top() + 8,
                    available.bottom() - menu_size.height() - 8,
                ),
            )

            menu.move(QPoint(menu_x, menu_y))

        place_menu_on_screen()
        menu.show()
        menu.raise_()

        def reopen_tutorial_menu():
            if not self.running:
                return

            if self.current_step() is not step:
                return

            if self._allow_tutorial_menu_close:
                return

            # Losing application focus deliberately hides the tutorial menu.
            # Do not immediately resurrect it while another program is active.
            if self._tutorial_app_inactive:
                return

            if self.tutorial_tools_menu is not menu:
                return

            try:
                place_menu_on_screen()

                # IMPORTANT: do not use QMenu.popup() here. popup() grabs
                # outside mouse clicks, so clicking the tutorial card's Back
                # or Skip buttons is swallowed by the menu. Keeping this
                # tutorial-only menu as a normal Tool window leaves the card
                # fully clickable.
                menu.show()
                menu.raise_()

                if action is not None:
                    menu.setActiveAction(action)

            except(
                RuntimeError,
                ReferenceError,
            ):
                pass

        def tutorial_menu_was_closed():
            if self._allow_tutorial_menu_close:
                return

            QTimer.singleShot(
                50,
                reopen_tutorial_menu,
            )

        menu.aboutToHide.connect(
            tutorial_menu_was_closed
        )

        def position_menu_tutorial():
            if (
                self.tutorial_tools_menu is None
                or not self.running
            ):
                return

            card = self.overlay.card
            overlay = self.overlay
            menu_rect = menu.frameGeometry()
            gap = 18

            screen = QApplication.screenAt(menu_rect.center())
            if screen is None:
                screen = QApplication.primaryScreen()
            available = screen.availableGeometry()

            # Prefer the card to the left of the menu. If there is not
            # enough room there, try the right. Finally clamp it so the
            # complete card remains visible on screen.
            card_x_global = menu_rect.left() - card.width() - gap
            if card_x_global < available.left() + 8:
                right_x = menu_rect.right() + gap
                if right_x + card.width() <= available.right() - 8:
                    card_x_global = right_x

            card_x_global = min(
                max(card_x_global, available.left() + 8),
                max(
                    available.left() + 8,
                    available.right() - card.width() - 8,
                ),
            )

            card_y_global = min(
                max(menu_rect.top(), available.top() + 8),
                max(
                    available.top() + 8,
                    available.bottom() - card.height() - 8,
                ),
            )

            local_pos = overlay.mapFromGlobal(
                QPoint(card_x_global, card_y_global)
            )

            card.move(local_pos)
            card.raise_()

        if action is not None:
            def safely_reselect_action(
                expected_menu=menu,
                expected_action=action,
                expected_step=step,
            ):
                # These timers can fire after Back/Skip/action selection has
                # already destroyed the tutorial QMenu.  Never dereference a
                # stale PySide wrapper.
                if (
                    not self.running
                    or self.current_step() is not expected_step
                    or self.tutorial_tools_menu is not expected_menu
                ):
                    return

                try:
                    expected_menu.setActiveAction(
                        expected_action
                    )
                except (
                    RuntimeError,
                    ReferenceError,
                ):
                    return

            QTimer.singleShot(
                0,
                safely_reselect_action,
            )

            QTimer.singleShot(
                80,
                safely_reselect_action,
            )

        QTimer.singleShot(
            0,
            position_menu_tutorial,
        )
        QTimer.singleShot(
            80,
            position_menu_tutorial,
        )

        # Keep the tutorial card above the popup visually.
        QTimer.singleShot(
            0,
            self.overlay.raise_,
        )
        QTimer.singleShot(
            0,
            self.overlay.card.raise_,
        )

    def _dialog_group_start_index(
        self,
        index,
    ):
        """
        Return the first index in the consecutive TutorialDialogStep group
        containing `index`, or None when the step is not a dialog step.
        """
        if (
            index < 0
            or index >= len(self.steps)
            or not isinstance(
                self.steps[index],
                TutorialDialogStep,
            )
        ):
            return None

        start = index

        while (
            start > 0
            and isinstance(
                self.steps[start - 1],
                TutorialDialogStep,
            )
        ):
            start -= 1

        return start

    def _dialog_opener_for_index(
        self,
        index,
    ):
        """
        Find the opener for the dialog group containing `index`.

        Later steps in a dialog group (for example Improvement Description)
        intentionally do not repeat open_dialog. This helper lets Back/Next
        recreate the correct dialog even after another tutorial dialog was
        opened in between.
        """
        group_start = self._dialog_group_start_index(
            index
        )

        if group_start is None:
            return None

        current = group_start

        while (
            current < len(self.steps)
            and isinstance(
                self.steps[current],
                TutorialDialogStep,
            )
        ):
            opener = getattr(
                self.steps[current],
                "open_dialog",
                None,
            )

            if opener is not None:
                return opener

            current += 1

        return None

    def _same_dialog_group(
        self,
        first_index,
        second_index,
    ):
        first_group = (
            self._dialog_group_start_index(
                first_index
            )
        )

        second_group = (
            self._dialog_group_start_index(
                second_index
            )
        )

        return (
            first_group is not None
            and first_group == second_group
        )

    def _close_current_tutorial_dialog_safely(
        self,
    ):
        self.overlay.restore_to_base_host()

        if hasattr(
            self.host,
            "close_tutorial_dialog",
        ):
            try:
                self.host.close_tutorial_dialog()
            except (
                RuntimeError,
                ReferenceError,
            ):
                pass

    def _show_dialog_step(
        self,
        step: TutorialDialogStep,
    ):
        dialog = step.dialog_getter()

        # A previous dialog may have been deleted while the Python
        # attribute still points to its wrapper.
        if dialog is not None:
            try:
                dialog.isVisible()
            except (
                RuntimeError,
                ReferenceError,
            ):
                dialog = None

        opener = (
            step.open_dialog
            or self._dialog_opener_for_index(
                self.index
            )
        )

        # No usable dialog exists: recreate the dialog belonging to this
        # entire dialog-step group.
        if dialog is None:
            if opener is None:
                self.next()
                return

            dialog = opener()

            if dialog is None:
                self.next()
                return

        try:
            self._run_before_show_once(
                step
            )

            target = step.target_getter(
                dialog
            )

            self._clear_enter_advance()

            if (
                step.advance_on_enter
                and hasattr(target, "returnPressed",)
            ):
                self._enter_advance_target = target

                target.returnPressed.connect(
                    self._advance_from_enter
                )

        except AttributeError:
            # We are holding the wrong dialog type. This most commonly
            # happens when the user presses Back across a boundary such as
            # Inventory -> Improvements. Close the current demo dialog and
            # recreate the one belonging to the destination step's group.
            if opener is None:
                raise

            self._close_current_tutorial_dialog_safely()

            dialog = opener()

            if dialog is None:
                self.next()
                return

            self._prepared_index = None
            self._run_before_show_once(
                step
            )

            target = step.target_getter(
                dialog
            )

        dialog.raise_()

        self.overlay.set_dialog_step(
            step,
            dialog,
            target,
            self.index,
            len(self.steps),
        )

        self.overlay.raise_()
        self.overlay.card.raise_()

    def _on_application_state_changed(self, state):
        """Hide tutorial-only floating UI while DID is not the active app."""
        inactive = (
            state
            != Qt.ApplicationState.ApplicationActive
        )

        self._tutorial_app_inactive = inactive

        if inactive:
            menu = self.tutorial_tools_menu
            if menu is not None:
                try:
                    menu.hide()
                except (RuntimeError, ReferenceError):
                    pass

            # Dialog tutorial steps can detach the instruction card into a
            # top-level Tool window. Hide it whenever DID is not the active
            # application so it never floats over another program.
            try:
                if self.overlay.card.isWindow():
                    self.overlay.card.hide()

                self.overlay.border_layer.hide()

            except (RuntimeError, ReferenceError):
                pass

            return

        # Rebuild/reposition whichever tutorial step is currently active.
        # _prepared_index prevents before_show setup from repeating merely
        # because application focus changed.
        if self.running:
            QTimer.singleShot(
                0,
                self.show_current,
            )

    def _close_tutorial_menu(self):
        if self.tutorial_tools_menu is None:
            return

        self._allow_tutorial_menu_close = True
        
        try:
            self.tutorial_tools_menu.close()
            self.tutorial_tools_menu.deleteLater()

        except (
            RuntimeError,
            ReferenceError,
        ):
            pass

        self.tutorial_tools_menu = None
        self._allow_tutorial_menu_close = False

    # ---------------------------------------------------------
    # Keep spotlight aligned when window changes
    # ---------------------------------------------------------

    def eventFilter(
        self,
        watched,
        event,
    ):
        if (
            self.running
            and watched is self.overlay_host
            and event.type()
            in {
                QEvent.Type.Resize,
                QEvent.Type.Move,
            }
        ):
            QTimer.singleShot(
                0,
                self.show_current,
            )

        return super().eventFilter(
            watched,
            event,
        )

    def check_completion(self):
        if not self.running:
            return

        step = self.current_step()

        if step is None:
            return

        check = getattr(
            step,
            "completion_check",
            None,
        )

        if check is None:
            return

        try:
            complete = bool(
                check()
            )
        except Exception:
            complete = False

        if complete:
            self.next()


    def _clear_enter_advance(
        self,
    ):
        target = self._enter_advance_target

        if target is None:
            return

        try:
            target.returnPressed.disconnect(
                self._advance_from_enter
            )
        except (
            RuntimeError,
            TypeError,
            ReferenceError,
        ):
            pass

        self._enter_advance_target = None


    def _advance_from_enter(
        self,
    ):
        if not self.running:
            return

        self._clear_enter_advance()

        QTimer.singleShot(
            0,
            self.next,
        )

# =============================================================
# DID CHARACTER SHEET WALKTHROUGH
# =============================================================

def build_did_tutorial(
    window,
) -> GuidedTutorial:

    def attr(name):
        return lambda: getattr(
            window,
            name,
            None,
        )

    def tutorial_dialog():
        return getattr(
            window,
            "tutorial_dialog",
            None,
        )

    def first_stat():
        rows = getattr(
            window,
            "stat_rows",
            {},
        )

        return rows.get(
            "agility"
        )

    def abilities_are_complete():
        dialog = tutorial_dialog()

        if dialog is None:
            return False

        remaining = getattr(
            dialog,
            "remaining_points",
            None,
        )

        if callable(remaining):
            try:
                remaining = remaining()

            except Exception:
                return False

        return remaining == 0

    def free_heightened_are_complete():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        used = len(
            getattr(
                character,
                "free_heightened_ability_stats",
                [],
            )
        )

        total = int(
            getattr(
                character,
                "free_heightened_ability_slots",
                2,
            )
        )

        return used >= total

    def species_is_chosen():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        improvements = getattr(
            character,
            "improvements",
            None,
        )

        if improvements is None:
            return False

        try:
            return bool(
                improvements.has_species_improvement()
            )
        except Exception:
            return False


    def character_already_named():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        name = str(
            getattr(
                character,
                "name",
                "",
            )
            or ""
        ).strip()

        return (
            bool(name)
            and name.casefold()
            != "unnamed character"
        )

    def abilities_already_complete():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        stats = getattr(
            character,
            "stats",
            None,
        )

        if stats is None:
            return False

        total_cost = 0

        try:
            for stat_name in STAT_NAMES:
                stat = stats.get_stat(
                    stat_name
                )

                if stat is None:
                    return False

                die_size = int(
                    stat.die_size
                )

                if die_size not in STAT_POINT_COSTS:
                    return False

                total_cost += int(
                    STAT_POINT_COSTS[
                        die_size
                    ]
                )

            budget = int(
                character.stat_point_budget
            )

        except Exception:
            return False

        return total_cost == budget

    def has_non_species_improvement():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        taken = getattr(
            getattr(
                character,
                "improvements",
                None,
            ),
            "list_of_taken_improvements",
            [],
        )

        return any(
            getattr(
                improvement,
                "source",
                "ip",
            ) != "species"
            for improvement in taken
        )

    def has_inventory_items():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        items = getattr(
            getattr(
                character,
                "inventory",
                None,
            ),
            "list_of_items",
            [],
        )

        return bool(items)

    def has_meaningful_notes():
        character = getattr(
            window,
            "character",
            None,
        )

        if character is None:
            return False

        notes = getattr(
            getattr(
                character,
                "notes",
                None,
            ),
            "list_of_notes",
            [],
        )

        return any(
            str(
                getattr(note, "title", "")
                or ""
            ).strip()
            or str(
                getattr(note, "text", "")
                or ""
            ).strip()
            for note in notes
        )

    # ---------------------------------------------------------
    # Name-step state
    #
    # Polling window.character.name was unreliable because that value is
    # updated by the QLineEdit's editingFinished signal.  Listen to the
    # real signal instead. Pressing Enter or leaving the field completes
    # the step, even when the text itself did not need to change.
    # ---------------------------------------------------------

    name_step_state = {
        "done": False,
        "connected": False,
    }

    def name_step_finished():
        name_step_state["done"] = True

    def prepare_name_step():
        field = getattr(
            window,
            "character_name_label",
            None,
        )

        if field is None:
            return

        if not name_step_state["connected"]:
            name_step_state["done"] = False

            field.editingFinished.connect(
                name_step_finished
            )

            name_step_state["connected"] = True

        # Give the real QLineEdit keyboard focus immediately. The user may
        # still click it normally through the rounded spotlight.
        QTimer.singleShot(
            0,
            field.setFocus,
        )

    def cleanup_name_step():
        field = getattr(
            window,
            "character_name_label",
            None,
        )

        if (
            field is not None
            and name_step_state["connected"]
        ):
            try:
                field.editingFinished.disconnect(
                    name_step_finished
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

        name_step_state["connected"] = False

    def name_step_is_complete():
        return bool(
            name_step_state["done"]
        )

    def show_ability_arrays_info_for_tutorial():
        dialog = tutorial_dialog()
        if dialog is None:
            return
        try:
            existing = getattr(dialog, "_arrays_info_window", None)
            if existing is None or not existing.isVisible():
                dialog.open_arrays_info()
        except (RuntimeError, ReferenceError, AttributeError):
            pass

    def close_ability_arrays_info_for_tutorial():
        dialog = tutorial_dialog()
        if dialog is None:
            return
        try:
            existing = getattr(dialog, "_arrays_info_window", None)
            if existing is not None:
                existing.close()
        except (RuntimeError, ReferenceError):
            pass

    steps = []

    # ---------------------------------------------------------
    # Tutorial philosophy
    # ---------------------------------------------------------
    # This is a guided tour, not a character-creation checklist.
    # Every step explains the real workflow and keeps the real controls
    # available, but the player never has to enter data or complete the
    # demonstrated action in order to continue.  Existing character data
    # therefore does not remove teaching steps from the tutorial.

    # ---------------------------------------------------------
    # Name
    # ---------------------------------------------------------

    steps.append(
        TutorialStep(
            title="Name Your Character",
            text=(
                "This is your character's name field. Click it whenever "
                "you want to enter or change the character's name, then "
                "press Enter when you are finished. You can try it now, "
                "or simply continue the tutorial."
            ),
            target=attr(
                "character_name_label"
            ),
            allow_interaction=True,
            before_show=prepare_name_step,
            after_complete=cleanup_name_step,
            tight_to_text=True,
        )
    )

    # ---------------------------------------------------------
    # Abilities
    # ---------------------------------------------------------

    steps.extend(
        [
            TutorialDialogStep(
                title="Ability Arrays",
                text=(
                    "The i button opens the suggested ability arrays. "
                    "The tutorial has opened them so you can see exactly "
                    "what this button shows. These examples can help you "
                    "decide how to distribute your ability dice. "
                    "Shortcut: Ctrl+E opens Edit Abilities."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.info_btn,
                open_dialog=(
                    window.open_ability_editor_for_tutorial
                ),
                interaction_mode="target",
                card_outside_dialog=True,
                before_show=show_ability_arrays_info_for_tutorial,
                after_complete=close_ability_arrays_info_for_tutorial,
            ),

            TutorialDialogStep(
                title="Reset Abilities",
                text=(
                    "The reset button returns all six abilities to d4. "
                    "Use it whenever you want to start your ability "
                    "choices again from scratch."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.reset_btn,
                interaction_mode="target",
                card_outside_dialog=True,
                spotlight_width=2,
            ),

            TutorialDialogStep(
                title="Ability Points",
                text=(
                    "This number shows your remaining Ability Points "
                    "and your total Ability Points. Higher dice cost "
                    "more points, so watch this number while building "
                    "your six abilities."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.points_label,
                interaction_mode="none",
                card_outside_dialog=True,
                spotlight_width=2,
            ),

            TutorialDialogStep(
                title="Choose Your Abilities",
                text=(
                    "Normally, choose the die for each ability until you "
                    "have used all of your Ability Points. The whole ability "
                    "grid is available so you can try it if you want, but "
                    "you can also press Next without changing anything."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    None,
                interaction_mode="all",
            ),

        ]
    )

    # ---------------------------------------------------------
    # Ability dice (optional demonstration, never roll automatically)
    # ---------------------------------------------------------

    steps.append(
        TutorialStep(
            title="Roll an Ability Die",
            text=(
                "When the Dice Roller is enabled, double-click an ability "
                "to roll its die. Right-click an ability to open Roll Options "
                "and choose extra advantage, disadvantage, or owned "
                "Improvement dice. Opposing advantage and disadvantage "
                "cancel each other. Only the main ability die explodes. "
                "You can try a roll now or press Next."
            ),
            target=first_stat,
            allow_interaction=True,
            padding=4,
        )
    )

    # ---------------------------------------------------------
    # Free Heightened Abilities
    # ---------------------------------------------------------

    character = getattr(
        window,
        "character",
        None,
    )

    free_used = len(
        getattr(
            character,
            "free_heightened_ability_stats",
            [],
        )
        or []
    )

    free_total = int(
        getattr(
            character,
            "free_heightened_ability_slots",
            2,
        )
        or 0
    )

    if free_used < free_total:
        steps.append(
            TutorialStep(
                title="Free Heightened Abilities",
                text=(
                    "This line is where you assign your two free Heightened "
                    "Ability increases. Click it and choose an ability when "
                    "building a character. You may choose the same ability "
                    "twice; the second increase on the same ability costs 1 IP. "
                    "You do not need to make either choice during the tutorial."
                ),
                target=attr(
                    "free_heightened_label"
                ),
                allow_interaction=True,
                tight_to_text=True,
                padding=6,
            )
        )

    # ---------------------------------------------------------
    # Improvements
    # ---------------------------------------------------------

    steps.extend(
        [
            TutorialStep(
                title="Improvements",
                text=(
                    "Improvements are the abilities, perks, and special "
                    "features you buy with IP. The Add Improvement button "
                    "opens the list of currently available choices."
                ),
                target=attr(
                    "add_improvement_btn"
                ),
            ),

            TutorialDialogStep(
                title="Filter Improvements",
                text=(
                    "Use Filter to narrow the list by type or tag. "
                    "The tutorial opens this picker in browse-only mode, "
                    "so looking around will not purchase anything."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.filter_combo,
                open_dialog=(
                    window.open_improvement_picker_for_tutorial
                ),
                interaction_mode="target",
                float_card_outside=True
            ),

            TutorialDialogStep(
                title="Search Improvements",
                text=(
                    "Type a name, rule, or tag here to search Improvements. "
                    "Search works together with the Filter selection. "
                    "This is browse-only during the tutorial, so searching "
                    "cannot purchase anything."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog: dialog.search_input,
                interaction_mode="target",
                float_card_outside=True,
            ),

            TutorialDialogStep(
                title="Browse Improvements",
                text=(
                    "Select an Improvement to inspect it. The list shows "
                    "its IP cost, and the description below explains what "
                    "it does. You can browse or simply continue."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.grid_scroll,
                interaction_mode="target",
                float_card_outside=True,
            ),

            TutorialDialogStep(
                title="Improvement Description",
                text=(
                    "Read the selected Improvement here. Bold text marks "
                    "important rules and costs."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.description_box,
                interaction_mode="none",
                after_complete=(
                    window.close_tutorial_dialog
                ),
                float_card_outside=True,
            ),
        ]
    )

    # ---------------------------------------------------------
    # Inventory
    # ---------------------------------------------------------

    steps.extend(
        [
            TutorialStep(
                title="Inventory",
                text=(
                    "Inventory keeps your character's items. The + button "
                    "opens the Add Item window. You can click it to see the "
                    "window yourself, or press Next and the tutorial will "
                    "open a demonstration copy for the next steps."
                ),
                target=attr(
                    "add_item_btn"
                ),
                allow_interaction=True,
                before_show=(
                    window.prepare_inventory_add_for_tutorial
                ),
                after_complete=(
                    window.restore_inventory_add_button_after_tutorial
                ),
            ),

            TutorialDialogStep(
                title="Item Name",
                text=(
                    "Enter a short name for the item here. In normal use, "
                    "this becomes the name shown in the Inventory list. "
                    "You can leave it blank during the tutorial."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.name_input,
                open_dialog=(
                    window.open_inventory_dialog_for_tutorial
                ),
                interaction_mode="target",
                float_card_outside=True,
            ),

            TutorialDialogStep(
                title="Item Quantity",
                text=(
                    "Quantity tracks how many copies of the item you have. "
                    "You can also adjust it later from the Inventory row. "
                    "There is no need to enter a value now."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.quantity_input,
                interaction_mode="target",
                float_card_outside=True,
            ),

            TutorialDialogStep(
                title="Item Description",
                text=(
                    "Use the description for the item's important details. "
                    "The arrow beside an Inventory item shows or hides this "
                    "text. You can leave the demonstration item empty."
                ),
                dialog_getter=tutorial_dialog,
                target_getter=lambda dialog:
                    dialog.description_input,
                interaction_mode="target",
                float_card_outside=True,
                after_complete=(
                    window.close_tutorial_dialog
                ),
            ),
        ]
    )

    # ---------------------------------------------------------
    # Species
    # ---------------------------------------------------------
    # If Creation Rules explicitly disable Species, there is no usable
    # Species workflow to demonstrate. Otherwise show the step even when
    # this character already has a Species: the tutorial teaches where the
    # command lives rather than checking character completion.

    species_disabled = (
        character is not None
        and getattr(
            character,
            "creation_rules_active",
            False,
        )
        and getattr(
            character,
            "creation_species_mode",
            "normal",
        ) == "disabled"
    )

    if not species_disabled:
        steps.append(
            TutorialMenuStep(
                title="Choose Your Species",
                text=(
                    "Species are added from the Tools menu. Choose Add "
                    "Species to select the Species improvement that fits "
                    "your character and enter the character's Species name. "
                    "You can open it now to look, or press Next without "
                    "adding or changing a Species."
                ),
                action_text="Add Species",
            )
        )

    # ---------------------------------------------------------
    # Resources
    # ---------------------------------------------------------

    steps.extend(
        [
            TutorialStep(
                title="Hearts",
                text=(
                    "Hearts track current HP. Each heart is divided into four "
                    "quarters. During normal use, click a quarter to set your "
                    "current HP. You do not need to change it now."
                ),
                target=attr(
                    "hp_panel"
                ),
            ),

            TutorialStep(
                title="Adversity Tokens",
                text=(
                    "The gold diamonds track Adversity Tokens (AT). During "
                    "normal use, click a diamond to set how many AT your "
                    "character currently has. You do not need to change it now."
                ),
                target=attr(
                    "at_box"
                ),
            ),
        ]
    )

    # ---------------------------------------------------------
    # Character / Notes page navigation
    # ---------------------------------------------------------

    steps.append(
        TutorialStep(
            title="Character and Notes Pages",
            text=(
                "These buttons switch between the main Character sheet "
                "and the dedicated Notes page. Choose Notes whenever you "
                "want more room for character information."
            ),
            target=attr(
                "notes_reopen_row"
            ),
            before_show=(
                window.show_character_page
            ),
            after_complete=(
                window.show_notes_for_tutorial
            ),
        )
    )

    # ---------------------------------------------------------
    # Notes
    # ---------------------------------------------------------

    steps.append(
        TutorialStep(
            title="Notes",
            text=(
                "This is the Notes page. The highlighted + button creates "
                "a new note. You can try it if you want, or press Next "
                "without creating anything."
            ),
            target=attr(
                "add_note_btn"
            ),
            allow_interaction=True,
            before_show=(
                window.show_notes_for_tutorial
            ),
            after_complete=(
                window.restore_notes_after_tutorial
            ),
        )
    )

    # ---------------------------------------------------------
    # Dice Roller fly-out: no real rolls or settings changes in the wizard.
    # ---------------------------------------------------------

    steps.append(
        TutorialMenuStep(
            title="Dice Roller Tools",
            text=(
                "Open Tools → Dice Roller. Enabled switches the 3D roller "
                "on or off. Roll Other Dice lets you choose quantities of "
                "d4, d6, d8, d10, d12, d20, and the single-piece physical "
                "d100, including mixed rolls. Previous Rolls (This Session) "
                "shows individual outcomes and totals until you close DID. "
                "This demonstration menu does not roll dice; press Next "
                "whenever you're ready."
            ),
            action_text="Dice Roller",
        )
    )

    # ---------------------------------------------------------
    # Other Tools, history, Level Up and Save
    # ---------------------------------------------------------

    steps.extend(
        [
            TutorialMenuStep(
                title="Adjust Resources",
                text=(
                    "Adjust Resources lets you directly change the character's "
                    "maximum Hearts, total IP, and maximum Adversity Tokens. "
                    "You can open it to see the controls or press Next."
                ),
                action_text="Adjust Resources",
            ),

            *(
                [
                    TutorialMenuStep(
                        title="Update Available",
                        text=(
                            "When a newer DID version is available, a bright "
                            "red Update Available button appears in Tools. "
                            "Choose it to review and download the update."
                        ),
                        action_text="Update Available",
                    )
                ]
                if getattr(
                    window,
                    "_available_update_release",
                    None,
                )
                else []
            ),

            TutorialStep(
                title="Undo and Redo",
                text=(
                    "Undo and Redo are available directly on the sheet. "
                    "Undo reverses the last character change; Redo reapplies "
                    "a change you just undid. Shortcuts: Ctrl+Z = Undo; "
                    "Ctrl+Y or Ctrl+Shift+Z = Redo. Hover either button later "
                    "to see its shortcut again."
                ),
                target=attr(
                    "undo_redo_frame"
                ),
            ),

            TutorialMenuStep(
                title="Earlier Versions",
                text=(
                    "Earlier Versions is now inside Tools. It lets you return "
                    "to an older saved state of the current character and "
                    "shows what restoring that version would change."
                ),
                action_text="Earlier Versions",
            ),

            TutorialMenuStep(
                title="Level Up",
                text=(
                    "When the GM gives you a level, choose Level Up from "
                    "Tools. It opens the real Level Up window. You can open "
                    "it to look, or press Next without leveling the character."
                ),
                action_text="Level Up",
            ),

            TutorialMenuStep(
                title="New Character",
                text=(
                    "New Character starts a fresh blank character sheet. "
                    "Shortcut: Ctrl+N. You do not need to create a new "
                    "character during the tutorial."
                ),
                action_text="New Character",
                before_show=(
                    window.restore_notes_after_tutorial
                ),
            ),

            TutorialMenuStep(
                title="Load Character",
                text=(
                    "Choose Load Character from Tools when you want to open "
                    "a saved character. Shortcuts: Ctrl+O or Ctrl+L. "
                    "You can open the real loader to look at it, or press Next."
                ),
                action_text="Load Character",
                before_show=(
                    window.restore_notes_after_tutorial
                ),
            ),

            TutorialMenuStep(
                title="Save Your Character",
                text=(
                    "Save Character is in the Tools menu. Shortcut: "
                    "Ctrl+S. You can use it now if you want, but saving is "
                    "not required to finish the tutorial."
                ),
                action_text="Save Character",
            ),
        ]
    )

    if not steps:
        steps.append(
            TutorialStep(
                title="You're Ready",
                text=(
                    "The character already has the setup information covered "
                    "by the tutorial. You can keep using the sheet normally."
                ),
                target=lambda: None,
            )
        )

    return GuidedTutorial(
        window,
        steps,
        parent=window,
    )
