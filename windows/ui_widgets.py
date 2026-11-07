from PySide6.QtCore import (
    Qt,
    QRect,
    Signal,
)

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QSpinBox,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
)

from ui_theme import (
    BLUE,
    set_themed_stylesheet,
)



class NumericEntry(QLineEdit):
    """A reliable, validated integer input for dialogs with no spin arrows.

    Standard QSpinBox editors were blank or uneditable under some combinations
    of inherited Qt styles and high-DPI Windows rendering.  This uses the same
    QLineEdit implementation as the working text fields, while preserving the
    range/value/valueChanged API that the existing dialog logic expects.
    """

    valueChanged = Signal(int)
    ButtonSymbols = QSpinBox.ButtonSymbols

    def __init__(self, parent=None):
        super().__init__(parent)
        self._low = 0
        self._high = 99
        self._last_value = 0
        self._validator = QIntValidator(self._low, self._high, self)
        self.setValidator(self._validator)
        self.setText("0")
        self.textChanged.connect(self._on_text_changed)
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

    def lineEdit(self):
        """Compatibility with code that configures QSpinBox.lineEdit()."""
        return self

    def setButtonSymbols(self, _symbols):
        """The number input deliberately has no native up/down arrows."""

    def setRange(self, minimum, maximum):
        self._low = int(minimum)
        self._high = max(self._low, int(maximum))
        self._validator.setRange(self._low, self._high)
        self.setValue(min(self._high, max(self._low, self.value())))

    def setMinimum(self, value):
        self.setRange(value, max(int(value), self._high))

    def setMaximum(self, value):
        self.setRange(min(self._low, int(value)), value)

    def minimum(self):
        return self._low

    def maximum(self):
        return self._high

    def setValue(self, value):
        number = max(self._low, min(self._high, int(value)))
        self.setText(str(number))

    def value(self):
        try:
            return max(self._low, min(self._high, int(self.text())))
        except ValueError:
            return self._low

    def _on_text_changed(self, text):
        if not text or text in ("+", "-"):
            return
        number = self.value()
        if number != self._last_value:
            self._last_value = number
            self.valueChanged.emit(number)

    def focusOutEvent(self, event):
        # Never leave an empty integer field when the user moves on.
        self.setValue(self.value())
        super().focusOutEvent(event)

class SmallTopBox(QFrame):
    """
    Displays a small rounded box with a title and a numeric value.
    Used for BDV, DR, and other small top‑row stats.
    """
    def __init__(self, title, value="0", color="#b8d8ea"):
        super().__init__()
        self.title = title

        self.setFixedSize(60, 90)
        set_themed_stylesheet(self, f"""
            QFrame {{
                background-color: {color};
                border: none;
                border-radius: 22px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        set_themed_stylesheet(self.title_label, """
            border: none;
            background: transparent;
            font-size: 15px;
            font-weight: 800;
            color: black;
        """)

        self.val = QLabel(value)
        self.val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val.setFixedSize(34, 34)
        set_themed_stylesheet(self.val, """
            background-color: white;
            border: none;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 800;
            color: black;
        """)
        
        layout.addStretch()
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(4)
        layout.addWidget(self.val, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def set_value(self, value: str):
        self.val.setText(value)
    
        
class EmbeddedArrowRow(QWidget):
    """
Shows a collapsible row with an arrow, a label, and a circular count badge.
Used for expandable sections like improvements or inventory.
    """
    def __init__(self, main_text, right_text):
        super().__init__()
        self.setMinimumHeight(70)
        self.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum
    )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # --- Middle blue box ---
        self.main_box = QFrame()
        set_themed_stylesheet(self.main_box, f"""
            background-color: {BLUE};
            border: 2px solid {BLUE};
            border-radius: 14px;
        """)
        self.main_box.setMinimumHeight(54)
        self.main_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        main_layout = QHBoxLayout(self.main_box)
        main_layout.setContentsMargins(14, 10, 16, 10)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        
        # --- TOP ROW (arrow + text) ---
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(3)
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.arrow_btn = QPushButton("▸")
        self.arrow_btn.setFixedSize(20, 20)
        self.arrow_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        set_themed_stylesheet(self.arrow_btn, """
            background-color: transparent;
            border: none;
            font-weight: bold;
            font-size: 18px;
            color: black;
            padding: 0px;
        """)

        self.label = QLabel(main_text)
        self.label.setWordWrap(False)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.label.setContentsMargins(0, 0, 0, 0)
        set_themed_stylesheet(self.label, """
            border: none;
            background: transparent;
            font-size: 18px;
            font-weight: 800;
            color: black;
            padding: 0px;
            margin: 0px;
        """)

        top_row.addWidget(self.arrow_btn, 0, Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(self.label, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()

        # push everything to top
        main_layout.addLayout(top_row)
        main_layout.addStretch()

        # --- Count circle outside main box ---
        self.count_box = QLabel(right_text)
        self.count_box.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.count_box.setFixedSize(42, 42)
        set_themed_stylesheet(self.count_box, f"""
            background-color: {BLUE};
            border: 2px solid {BLUE};
            border-radius: 21px;
            font-weight: bold;
        """)

        outer.addWidget(self.main_box, 1)
        outer.addWidget(self.count_box, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_texts(self, main_text: str, right_text: str):
        self.label.setText(main_text)
        self.count_box.setText(right_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        box_geom = self.main_box.geometry()
        arrow_x = box_geom.x() + 6
        arrow_y = box_geom.y() + 6
        self.arrow_btn.move(arrow_x, arrow_y)


class BigPlusButton(QPushButton):
    """
    A large stylized “+” button used for adding new items or entries.
    Expands horizontally and uses a bold, attention‑grabbing design.
    """
    def __init__(self, text="+"):
        super().__init__(text)

        self.setFixedHeight(54)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        set_themed_stylesheet(self, f"""
            QPushButton {{
                background-color: {BLUE};
                border: 3px solid black;
                border-radius: 18px;
                font-size: 32px;
                font-weight: 900;
                color: black;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}

            QPushButton:pressed {{
                background-color: #9fcfe3;
            }}
        """)

        
class IPLabel(QLabel):
    """
    A label that grants IP when double‑clicked.
    Acts as a quick‑access shortcut for awarding improvement points.
    """
    def mouseDoubleClickEvent(self, event):
        window = self.window()
        if callable(getattr(window, "is_campaign_character_for_tools", None)) and window.is_campaign_character_for_tools():
            event.accept()
            return
        window.grant_ip_from_ui()
        event.accept()

class AutoWrapLabel(QLabel):
    """
    QLabel that:
    - stays on one line when the text fits;
    - wraps automatically when it does not;
    - reports the correct height for its current width;
    - never expands its parent horizontally just to fit the text.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

        self.setWordWrap(True)

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if width <= 0:
            return self.sizeHint().height()

        rect = self.fontMetrics().boundingRect(
            QRect(
                0,
                0,
                int(width),
                10000,
            ),
            Qt.TextFlag.TextWordWrap,
            self.text(),
        )

        return rect.height() + 4

    def sizeHint(self):
        hint = super().sizeHint()

        if self.width() > 0:
            hint.setHeight(
                self.heightForWidth(
                    self.width()
                )
            )

        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(0)

        if self.width() > 0:
            hint.setHeight(
                self.heightForWidth(
                    self.width()
                )
            )

        return hint
