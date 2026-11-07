from ui_feedback import cached_portrait
import math
import base64

from PySide6.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    QByteArray,
    QBuffer,
    QIODevice,
)

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QToolTip,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QDialog,
)

from PySide6.QtGui import (
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QPolygonF,
    QColor,
    QCursor,
    QPixmap
)

from backend_2_1 import (
    Character,
    HPSystem,
    ATSystem,
    ImageSystem,
    STAT_NAMES,
    ImprovementSystem,
    ImprovementCatalogSystem,
)

from dialogs import (
    AbilityEditorDialog,
    ImprovementPickerDialog,
    ChoiceInputDialog,
    ask_yes_no,
)

from ui_theme import (
    BLUE,
    theme_color,
    set_themed_stylesheet,
    fantasy_text_input,
)
from ui_widgets import (
    SmallTopBox,
)
REGULAR_SHEET_HEIGHT = (6 * 92) + (5 * 8)  # 6 stat boxes + 5 gaps = 592
CENTER_TOP_HEIGHT = 70 + 90                # hearts + AT/BDV/DR row
PICTURE_BOX_HEIGHT = REGULAR_SHEET_HEIGHT - CENTER_TOP_HEIGHT

def fit_image_to_frame(pixmap: QPixmap, width: int, height: int) -> QPixmap:
    """
    Fits the entire image inside the requested frame.
    No cropping.
    No stretching.
    White padding is added where necessary.
    """

    result = QPixmap(width, height)
    result.fill(Qt.GlobalColor.white)

    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    painter = QPainter(result)

    x = (width - scaled.width()) // 2
    y = (height - scaled.height()) // 2

    painter.drawPixmap(x, y, scaled)
    painter.end()

    return result
    
class StatCol(QFrame):
    """
    Displays one stat (like STR, DEX, etc.) with a big die icon and a small bonus box.
    Reads from the character model and updates the UI.
    """
    def __init__(self, stat_label: str, stat_key: str, character: Character):
        super().__init__()
        self.stat_label = stat_label
        self.stat_key = stat_key
        self.character = character

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        

        self.ability_descriptions = {
            "agility": """Controls speed and quick movement.
Use it to run fast, jump gaps, or dodge danger.""",
            
            "strength": """Measures muscle power and toughness.
Use it to break barriers, lift heavy objects, or fight foes.""",
            
            "finesse": """Controls careful and steady movement.
Use it to fix tools, hide, or aim accurately.""",
            
            "instinct": """Controls awareness and gut feelings.
Use it to spot danger, find your way, or read people.""",

            "presence": """Measures personality and social power.
Use it to charm friends, trick others, or scare enemies.""",
            
            "knowledge": """Tracks memory and smart thinking.
Use it to study clues, remember facts, or solve puzzles."""
        }
                
        self.ability_tooltip_text = self.ability_descriptions.get(self.stat_key, "")

        self.ability_tooltip_timer = QTimer(self)
        self.ability_tooltip_timer.setSingleShot(True)
        self.ability_tooltip_timer.setInterval(500)

        self.ability_tooltip_timer.timeout.connect(
            self.show_ability_tooltip
        )
        self.setMouseTracking(True)


        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(92)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 20, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.label_box = QFrame(self)
        self.label_box.setFixedSize(78, 78)
        set_themed_stylesheet(self.label_box, f"""
            QFrame {{
                background-color: {BLUE};
                border: 2px solid black;
                border-radius: 12px;
            }}
        """)

        box_layout = QVBoxLayout(self.label_box)
        box_layout.setContentsMargins(4, 4, 4, 4)
        box_layout.setSpacing(0)

        self.center_label = QLabel()
        self.center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.center_label, """
            border: none;
            background: transparent;
            font-size: 25px;
            font-weight: bold;
        """)

        self.bottom_label = QLabel(self.stat_label)
        self.bottom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.bottom_label, """
            border: none;
            background: transparent;
            font-size: 12px;
            font-weight: bold;
        """)

        box_layout.addStretch()
        box_layout.addWidget(self.center_label)
        box_layout.addStretch()
        box_layout.addWidget(self.bottom_label)

        # Small box
        self.small_box = QLabel(self)
        self.small_box.setFixedSize(28, 28)
        self.small_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.small_box, f"""
            QLabel {{
                background-color: {BLUE};
                border: 2px solid black;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }}
        """)

        layout.addWidget(
            self.label_box,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.small_box.raise_()
        self.refresh()

    def get_stat(self):
        return self.character.stats.get_stat(self.stat_key)

    def refresh(self):
        stat = self.get_stat()
        if stat is None:
            self.center_label.setText("?")
            self.small_box.setText("?")
            return
        self.center_label.setText(f"d{stat.die_size}")
        self.small_box.setText(f"+{stat.bonus}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.label_box.geometry()
        s = self.small_box.width()
        self.small_box.move(rect.right() - s // 2, rect.top() - s // 2)

    def enterEvent(self, event):
        if self.ability_tooltip_text:
            self.ability_tooltip_timer.start()

        super().enterEvent(event)


    def leaveEvent(self, event):
        self.ability_tooltip_timer.stop()
        QToolTip.hideText()

        super().leaveEvent(event)


    def show_ability_tooltip(self):
        if self.underMouse() and self.ability_tooltip_text:
            QToolTip.showText(
                QCursor.pos(),
                self.ability_tooltip_text,
                self,
                self.rect(),
                60000,
            )
    def mouseMoveEvent(self, event):
        if self.ability_tooltip_text:
            QToolTip.showText(
                QCursor.pos(),
                self.ability_tooltip_text,
                self,
                self.rect(),
                60000,
            )

        super().mouseMoveEvent(event)


class HeartWidget(QWidget):
    """
    Draws a single heart divided into four clickable HP quarters.
    Handles painting, filling, and detecting which quarter the user clicked.
    """

    def __init__(self, heart_index, quarter_click_callback):
        super().__init__()
        self.heart_index = heart_index
        self.quarter_click_callback = quarter_click_callback
        self.filled_quarters = 0
        self.available_quarters = 4
        self.setMinimumSize(16, 16)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_filled_quarters(self, count):
        self.filled_quarters = max(0, min(4, count))
        self.update()

    def set_available_quarters(self, count):
        self.available_quarters = max(0, min(4, count))
        self.update()

    def mousePressEvent(self, event):
        x = event.position().x()
        y = event.position().y()
        mid_x = self.width() / 2
        split_y = self.height() * 0.42

        if y < split_y:
            quarter_index = 0 if x < mid_x else 1
        else:
            quarter_index = 2 if x < mid_x else 3

        if quarter_index >= self.available_quarters:
            return

        self.quarter_click_callback(self.heart_index, quarter_index)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        heart_path = self.build_heart_path()
        quarter_paths = self.build_quarter_paths()

        # Base heart
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QBrush(QColor(theme_color("heart_empty")))
        )
        painter.drawPath(heart_path)

        # Locked unavailable quarters
        painter.setBrush(
            QBrush(QColor(theme_color("heart_locked")))
        )
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(self.available_quarters, 4):
            locked_piece = heart_path.intersected(quarter_paths[i])
            painter.drawPath(locked_piece)

        # Fill HP quarters
        painter.setBrush(
            QBrush(QColor(theme_color("heart_fill")))
        )
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(min(self.filled_quarters, self.available_quarters)):
            filled_piece = heart_path.intersected(quarter_paths[i])
            painter.drawPath(filled_piece)

        # Outline
        painter.setPen(
            QPen(QColor(theme_color("heart_outline")), 2)
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(heart_path)

        # Quarter divider lines
        split_y = self.height() * 0.50
        painter.drawLine(
            int(self.width() * 0.5), int(self.height() * 0.15),
            int(self.width() * 0.5), int(self.height() * 0.95)
        )
        painter.drawLine(
            int(self.width() * 0.12), int(split_y),
            int(self.width() * 0.9), int(split_y)
        )

    def build_heart_path(self):
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.moveTo(w * 0.50, h * 0.20)
        path.cubicTo(w * 0.50, h * 0.04, w * 0.78, h * 0.02, w * 0.88, h * 0.22)
        path.cubicTo(w * 0.98, h * 0.42, w * 0.88, h * 0.70, w * 0.50, h * 0.95)
        path.cubicTo(w * 0.12, h * 0.70, w * 0.02, h * 0.42, w * 0.12, h * 0.22)
        path.cubicTo(w * 0.22, h * 0.02, w * 0.50, h * 0.04, w * 0.50, h * 0.20)
        path.closeSubpath()
        return path

    def build_quarter_paths(self):
        w, h = self.width(), self.height()
        mid_x = w * 0.5
        split_y = h * 0.5
        return [
            self._path_rect(0, 0, mid_x, split_y),
            self._path_rect(mid_x, 0, w - mid_x, split_y),
            self._path_rect(0, split_y, mid_x, h - split_y),
            self._path_rect(mid_x, split_y, w - mid_x, h - split_y),
        ]

    def _path_rect(self, x, y, w, h):
        p = QPainterPath()
        p.addRect(QRectF(x, y, w, h))
        return p


class HeartsPanel(QFrame):
    """
    Arranges all HeartWidgets into rows and auto‑sizes them to fit a fixed area.
    Updates filled/available HP based on the character’s current and max HP.
    """
    def __init__(self, character):
        super().__init__()
        self.character = character
        self.heart_widgets = []

        # --- Heart sizing ---
        self.normal_heart_width = 78
        self.normal_heart_height = 72
        self.min_heart_width = 16
        self.heart_gap = 4

        # --- Invisible box size ---
        # Width = space that normally fits 5 full hearts
        self.box_width = (7 * self.normal_heart_width) + (6 * self.heart_gap)

        # Height = fixed area reserved for the hearts.
        # Change this number if you want the heart area taller/shorter.
        self.box_height = 70

        self.setFixedSize(self.box_width, self.box_height)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(self.heart_gap)
        self.main_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.rebuild_hearts()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)

            child_widget = item.widget()
            if child_widget is not None:
                child_widget.deleteLater()
                continue

            child_layout = item.layout()
            if child_layout is not None:
                self.clear_layout(child_layout)

    def refresh_hearts(self):
        self.character.validate()

        remaining_filled = self.character.HP.current_HP
        remaining_available = self.character.HP.max_HP

        for heart in self.heart_widgets:
            available = max(0, min(4, remaining_available))
            filled = max(0, min(available, remaining_filled))

            heart.set_available_quarters(available)
            heart.set_filled_quarters(filled)

            remaining_available -= available
            remaining_filled -= filled

    def calculate_best_arrangement(self, count):
        """
        Try every possible row count from 1 to count.
        Pick the one that allows the largest heart size
        inside the fixed box.
        """
        best_rows = 1
        best_width = self.min_heart_width
        best_height = int(
            self.min_heart_width * self.normal_heart_height / self.normal_heart_width
        )

        for rows in range(1, count + 1):
            hearts_in_widest_row = (count + rows - 1) // rows

            # Horizontal limit
            total_h_gap = self.heart_gap * (hearts_in_widest_row - 1)
            available_width = self.box_width - total_h_gap
            if available_width <= 0:
                continue
            width_limited_heart_width = available_width / hearts_in_widest_row

            # Vertical limit
            total_v_gap = self.heart_gap * (rows - 1)
            available_height = self.box_height - total_v_gap
            if available_height <= 0:
                continue
            max_heart_height = available_height / rows
            height_limited_heart_width = (
                max_heart_height * self.normal_heart_width / self.normal_heart_height
            )

            candidate_width = min(
                self.normal_heart_width,
                width_limited_heart_width,
                height_limited_heart_width,
            )

            if candidate_width < self.min_heart_width:
                continue

            candidate_height = (
                candidate_width * self.normal_heart_height / self.normal_heart_width
            )

            if candidate_width > best_width:
                best_rows = rows
                best_width = candidate_width
                best_height = candidate_height

        return best_rows, int(round(best_width)), int(round(best_height))

    def rebuild_hearts(self):
        self.clear_layout(self.main_layout)
        self.heart_widgets.clear()

        count = math.ceil(self.character.HP.max_HP / 4)

        if count <= 0:
            return

        # Zelda-style hearts Layout
        two_row_hearts_height = (
            self.box_height - self.heart_gap
        ) / 2

        two_row_heart_width = (
            two_row_hearts_height
            * self.normal_heart_width
            / self.normal_heart_height
        )

        hearts_per_full_row = max(
            1,
            int(
                (self.box_width + self.heart_gap)
                // (two_row_heart_width + self.heart_gap)
            ),
        )

        if count <= hearts_per_full_row:
            row = 1 # max 13 Level
            hearts_per_row = count

            total_gap_width = self.heart_gap * (count - 1)

            heart_width = (
                self.box_width - total_gap_width
            ) / count

            heart_width = min(
                self.normal_heart_width,
                heart_width,
            )

            heart_height = (
                heart_width
                * self.normal_heart_height
                / self.normal_heart_width
            )

        else:
            rows = 2 # max 27 Level
            hearts_per_row = hearts_per_full_row

            heart_width = two_row_heart_width
            heart_height = two_row_hearts_height

        heart_width = int(round(heart_width))
        heart_height = int(round(heart_height))

        heart_index = 0
        remaining = count
        
        while remaining > 0:
            row_count = min(hearts_per_row, remaining)

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self.heart_gap)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for _ in range(row_count):
                heart = HeartWidget(
                    heart_index,
                    self.on_heart_quarter_click
                )
                heart.setFixedSize(heart_width, heart_height)
                
                self.heart_widgets.append(heart)
                row_layout.addWidget(heart)

                heart_index += 1

            self.main_layout.addLayout(row_layout)

            remaining -= row_count

        self.refresh_hearts()

    def on_heart_quarter_click(self, heart_index, quarter_index):
        window = self.window()

        if hasattr(window, "block_if_readonly") and window.block_if_readonly():
            return
        
        new_hp = (heart_index * 4) + (quarter_index + 1)

        if new_hp > self.character.HP.max_HP:
            return
        
        HPSystem.set_HP(self.character, new_hp)
        self.refresh_hearts()
        window = self.window()
        window.mark_dirty()


class ATWidget(QWidget):
    """
    Shows AT (Adversity Tokens) as clickable golden diamonds.
    Auto‑sizes the diamonds and updates the character’s AT when clicked.
"""
    def __init__(self, character: Character):
        super().__init__()
        self.character = character

        self.setMinimumHeight(72)
        self.setMinimumWidth(390)
        
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def calculate_layout(self, count):
        # Zelda-style AT Layout
        edge_margin = 2

        normal_h_gap = 8
        small_h_gap = 4
        v_gap = 4

        rect = QRectF(
            0,
            0,
            self.width(),
            self.height(),
        ).adjusted(
            edge_margin,
            edge_margin,
            -edge_margin,
            -edge_margin,
        )

        if count <= 0:
            return {
                "rect": rect,
                "rows": 0,
                "per_row": 0,
                "diamond_size": 0,
                "h_gap": small_h_gap,
                "v_gap": v_gap,
                "start_x": rect.left(),
                "start_y": rect.top(),
            }

        two_row_diamond_size = (
            rect.height() - v_gap
        ) / 2

        max_per_row = max(
            1,
            int(
                (rect.width() + small_h_gap)
                // (
                    two_row_diamond_size
                    + small_h_gap
                )
            ),
        )

        if count <= max_per_row:
            rows = 1 # Level 9
            per_row = count

            h_gap = normal_h_gap

            available_width = (
                rect.width()
                - h_gap * (count - 1)
            )

            diamond_size = available_width / count

            normal_max_size = rect.height() * 0.85

            diamond_size = min(
                diamond_size,
                normal_max_size,
            )

            if diamond_size < two_row_diamond_size:
                h_gap = small_h_gap

                available_width = (
                    rect.width()
                    - h_gap * (count - 1)
                )

                diamond_size = max(
                    two_row_diamond_size,
                    diamond_size,
                )

            start_y = (
                rect.top()
                + (rect.height() - diamond_size) / 2
            )


        else:
            rows = 2 # Level 21
            per_row = max_per_row

            h_gap = small_h_gap
            diamond_size = two_row_diamond_size

            start_y = rect.top()
            
        start_x = rect.left()

        return {
            "rect": rect,
            "rows": rows,
            "per_row": per_row,
            "diamond_size": diamond_size,
            "slot_width": diamond_size,
            "slot_height": diamond_size,
            "h_gap": h_gap,
            "v_gap": v_gap,
            "start_x": start_x,
            "start_y": start_y,
        }


    def mousePressEvent(self, event):
        count = self.character.adversity.max_AT

        if count <= 0:
            return

        layout = self.calculate_layout(count)

        per_row = layout["per_row"]
        diamond_size = layout["diamond_size"]
        h_gap = layout["h_gap"]
        v_gap = layout["v_gap"]
        start_x = layout["start_x"]
        start_y = layout["start_y"]

        if per_row <= 0 or diamond_size <= 0:
            return

        click_pos = event.position()
        half = diamond_size / 2

        clicked_index = None

        for i in range(count):
            row = i // per_row
            col = i % per_row

            cx = (
                start_x
                + half
                + col * (diamond_size + h_gap)
            )

            cy = (
                start_y
                + half
                + row * (diamond_size + v_gap)
            )

            diamond = QPolygonF([
                QPointF(cx, cy - half),
                QPointF(cx + half, cy),
                QPointF(cx, cy + half),
                QPointF(cx - half, cy),
            ])

            if diamond.containsPoint(
                click_pos,
                Qt.FillRule.WindingFill,
            ):
                clicked_index = i
                break

        if clicked_index is None:
            return

        window = self.window()

        if (
            hasattr(window, "block_if_readonly")
            and window.block_if_readonly()
        ):
            return

        ATSystem.click_at_slot(
            self.character,
            clicked_index,
        )

        window.mark_dirty()
        self.update()
        window.refresh_top_boxes()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        count = self.character.adversity.max_AT
        current = self.character.adversity.current_AT

        if count <= 0:
            return

        layout = self.calculate_layout(count)

        per_row = layout["per_row"]
        diamond_size = layout["diamond_size"]
        h_gap = layout["h_gap"]
        v_gap = layout["v_gap"]
        start_x = layout["start_x"]
        start_y = layout["start_y"]

        half = diamond_size / 2

        for i in range(count):
            row = i // per_row
            col = i % per_row

            cx = start_x + half + col * (diamond_size + h_gap)
            cy = start_y + half + row * (diamond_size + v_gap)

            diamond = QPolygonF([
                QPointF(cx, cy - half),
                QPointF(cx + half, cy),
                QPointF(cx, cy + half),
                QPointF(cx - half, cy),
            ])

            if i < current:
                painter.setBrush(
                    QBrush(QColor(theme_color("at_fill")))
                )
                painter.setPen(
                    QPen(QColor(theme_color("at_fill_border")), 2)
                )
            else:
                painter.setBrush(
                    QBrush(QColor(theme_color("at_empty")))
                )
                painter.setPen(
                    QPen(QColor(theme_color("at_empty_border")), 2)
                )

            painter.drawPolygon(diamond)

class ImageMixin:
    def build_character_image_carousel(self, center_col):
        self.image_frame = QFrame()
        self.image_frame.setFixedHeight(PICTURE_BOX_HEIGHT)
        set_themed_stylesheet(self.image_frame, """
            QFrame {
                background-color: #eeeeee;
                border: 3px solid black;
                border-radius: 18px;
            }
        """)

        image_layout = QVBoxLayout(self.image_frame)
        image_layout.setContentsMargins(12, 2, 12, 12)
        image_layout.setSpacing(8)

        self.image_label = QLabel("+")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(0)
        set_themed_stylesheet(self.image_label, """
            QLabel {
                background-color: white;
                border: 2px dashed black;
                border-radius: 14px;
                font-size: 72px;
                font-weight: 900;
                color: black;
            }
        """)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.remove_image_btn = QPushButton("x", self.image_label)
        self.remove_image_btn.setFixedSize(22, 22)
        self.remove_image_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        font = self.remove_image_btn.font()
        font.setPointSize(10)
        font.setBold(True)

        set_themed_stylesheet(self.remove_image_btn, """
            QPushButton {
                background-color: none;
                color: black;
                border: none;
                border-radius: 11px;
                padding: 0px;
            }

            QPushButton:hover {
                background-color: none;
            }

            QPushButton:pressed {
                background-color: #b71c1c;
            }
            """)
        self.remove_image_btn.clicked.connect(
            self.confirm_remove_character_image
        )
        self.remove_image_btn.hide()

        self.image_label.mousePressEvent = (
            lambda event: self.add_character_image_from_ui()
        )

        image_layout.addWidget(self.image_label, 1)

        image_controls = QHBoxLayout()
        image_controls.setSpacing(8)

        self.prev_image_btn = QPushButton("<")
        self.next_image_btn = QPushButton(">")
        self.add_image_btn = QPushButton("+")
        self.image_counter_label = QLabel("0 / 0")

        self.prev_image_btn.clicked.connect(self.previous_character_image)
        self.next_image_btn.clicked.connect(self.next_character_image)
        self.add_image_btn.clicked.connect(self.add_character_image_from_ui)

        self.image_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.image_counter_label, """
            border: none;
            background: transparent;
            font-size: 14px;
            font-weight: 900;
            color: black;
        """)

        for btn in (
            self.prev_image_btn,
            self.next_image_btn,
            self.add_image_btn,
        ):
            btn.setFixedSize(42, 34)
            set_themed_stylesheet(btn, f"""
                QPushButton {{
                    background-color: {BLUE};
                    border: 2px solid black;
                    border-radius: 10px;
                    font-size: 18px;
                    font-weight: 900;
                    color: black;
                }}

                QPushButton:hover {{
                    background-color: #d8eef8;
                }}
            """)

        image_controls.addWidget(self.prev_image_btn)
        image_controls.addWidget(self.image_counter_label, 1)
        image_controls.addWidget(self.next_image_btn)
        image_controls.addWidget(self.add_image_btn)

        image_layout.addLayout(image_controls)

        center_col.addWidget(self.image_frame, 1, Qt.AlignmentFlag.AlignTop)


    def refresh_character_image(self):
        image_entry = self.character.image.current_image()

        if isinstance(image_entry, dict):
            image_data = (
                image_entry.get("display")
                or image_entry.get("original")
            )
        else:
            image_data = image_entry

        total = len(self.character.image.images)

        if total == 0 or not image_data:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("+")
            self.image_counter_label.setText("0 / 0")
            self.prev_image_btn.setEnabled(False)
            self.next_image_btn.setEnabled(False)
            self.remove_image_btn.hide()

            set_themed_stylesheet(self.image_label, """
                QLabel {
                    background-color: white;
                    border: 2px dashed black;
                    border-radius: 14px;
                    font-size: 72px;
                    font-weight: 900;
                    color: black;
                }
            """)
            return

        self.image_label.setText("")

        try:
            cropped = cached_portrait(image_data, self.image_label.width(), self.image_label.height())

            set_themed_stylesheet(self.image_label, """
                QLabel {
                    background-color: white;
                    border: none;
                    border-radius: 14px;
                }
            """)

            self.image_label.setPixmap(cropped)

        except Exception:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Image Error")

        current = self.character.image.current_index + 1
        self.image_counter_label.setText(f"{current} / {total}")

        self.prev_image_btn.setEnabled(total > 1)
        self.next_image_btn.setEnabled(total > 1)

        self.remove_image_btn.show()
        self.remove_image_btn.move(
            self.image_label.width() - self.remove_image_btn.width() - 8,
            8
        )
        self.remove_image_btn.raise_()


    def add_character_image_from_ui(self):
        if self.block_if_readonly():
            return
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Character Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if not filepath:
            return

        try:
            pixmap = QPixmap(filepath)

            if pixmap.isNull():
                QMessageBox.warning(
                    self,
                    "Invalid Image",
                    "Could not load this image."
                )
                return
            
            display_pixmap = fit_image_to_frame(
                pixmap,
                self.image_label.width(),
                self.image_label.height(),
            )

            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)

            display_pixmap.save(buffer, "PNG")

            cropped_image_data = (
                "data:image/png;base64,"
                + base64.b64encode(byte_array.data()).decode("utf-8")
            )

            with open(filepath, "rb") as file:
                raw_data = file.read()

            encoded = base64.b64encode(raw_data).decode("utf-8")
            extension = filepath.lower().split(".")[-1]

            if extension in ("jpg", "jpeg"):
                image_type = "jpg"
            elif extension == "png":
                image_type = "png"
            elif extension == "bmp":
                image_type = "bmp"
            elif extension == "gif":
                image_type = "gif"
            else:
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "Please choose a valid image file."
                )
                return

            original_image_data = f"data:image/{image_type};base64,{encoded}"

            ImageSystem.add_image(
                self.character,
                {
                    "original": original_image_data,
                    "display": cropped_image_data,
                }
            )

            self.mark_dirty(auto_save=True)
            self.refresh_all()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Image Error",
                f"Could not load image:\n{error}"
            )

    def remove_character_image(self):
        if self.block_if_readonly():
            return
        
        images = self.character.image.images

        if not images:
            return

        current_index = self.character.image.current_index

        del images[current_index]

        if images:
            self.character.image.current_index = min(
                current_index,
                len(images) - 1
            )
        else:
            self.character.image.current_index = 0

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def confirm_remove_character_image(self):
        if self.block_if_readonly():
            return
        
        if not self.character.image.images:
            return
        
        if not ask_yes_no(
            self,
            "Remove Image",
            "Are you sure you want to remove this image?",
        ):
            return

        self.remove_character_image()

    def previous_character_image(self):
        ImageSystem.previous_image(self.character)
        self.refresh_character_image()

    def next_character_image(self):
        ImageSystem.next_image(self.character)
        self.refresh_character_image()

class CharacterDisplayMixin:
    def build_stats_column(self, main_layout):
        self.stats_col = QVBoxLayout()
        self.stats_col.setSpacing(8)
        self.stats_col.setContentsMargins(0, 0, 0, 0)
        self.stats_col.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.stat_rows = {}

        stat_display_names = {
            "agility": "Agility",
            "strength": "Strength",
            "finesse": "Finesse",
            "instinct": "Instinct",
            "presence": "Presence",
            "knowledge": "Knowledge",
        }
        
        for stat_key in STAT_NAMES:
            row = StatCol(
                stat_display_names[stat_key],
                stat_key,
                self.character
            )
            
            self.stat_rows[stat_key] = row

        self.refresh_stats()

        stat_widget = QWidget()

        stat_widget.setLayout(self.stats_col)
        stat_widget.setFixedHeight(REGULAR_SHEET_HEIGHT)
        stat_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        
        main_layout.addWidget(
            stat_widget,
            1,
            Qt.Alignment.AlignTop,
        )

    def build_center_column(self, main_layout):
        center_widget = QWidget()

        center_widget.setFixedHeight(REGULAR_SHEET_HEIGHT)
        center_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        center_col = QVBoxLayout(center_widget)
        center_col.setContentsMargins(0, 0, 0, 0)
        center_col.setSpacing(0)

     
        # ---------------- Hearts ----------------

        self.hp_panel = HeartsPanel(self.character)
        center_col.addWidget(
            self.hp_panel,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
        )

        # ---------------- AT / BDV / DR ----------------

        boxes = QHBoxLayout()
        boxes.setSpacing(6)
        boxes.setContentsMargins(0, 0, 0, 0)
        boxes.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.at_box = ATWidget(self.character)
        self.bdv_box = SmallTopBox("BDV", "0")
        self.dr_box = SmallTopBox("DR", "0")

        boxes.addWidget(self.at_box, 1)
        boxes.addWidget(self.bdv_box, 0)
        boxes.addWidget(self.dr_box, 0)

        center_col.addLayout(boxes)

        # ---------------- Character Image ----------------

        self.build_character_image_carousel(center_col)

        main_layout.addWidget(
            center_widget,
            4,
            Qt.AlignmentFlag.AlignTop
        )

    def calculate_bdv(self) -> int:
        return self.character.BDV

    def calculate_dr(self) -> int:
        return self.character.DR

    def refresh_stats(self):
        sorted_stats = sorted(
            STAT_NAMES,
            key=lambda stat_name: (
                -self.character.stats.get_stat(stat_name).die_size,
                -self.character.stats.get_stat(stat_name).bonus,
                stat_name,
            )
        )

        while self.stats_col.count():
            item = self.stats_col.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)

        for stat_name in sorted_stats:
            row = self.stat_rows[stat_name]
            row.refresh()

            self.stats_col.addWidget(
                row,
                0,
                Qt.AlignmentFlag.AlignLeft
            )

    def refresh_top_boxes(self):
        self.at_box.update()

        # ---------------- BDV tooltip ----------------
        self.bdv_box.set_value(str(self.calculate_bdv()))
        max_at = self.character.adversity.max_AT
        self.bdv_box.setToolTip(
            f"Max AT {max_at} ÷ 2 = {self.character.BDV}"
        )
        
        # ---------------- DR tooltip ----------------
        self.dr_box.set_value(str(self.calculate_dr()))
        defense_stat_name = self.character.defense_stat_name
        defense_stat = self.character.stats.get_stat(defense_stat_name)

        if defense_stat is not None:
            stat_name = defense_stat_name.title()
            die_size = defense_stat.die_size
            bonus = defense_stat.bonus

            if bonus:
                dr_tooltip = (
                    f"{stat_name} d{die_size} ÷ 2 + {bonus} = "
                    f"{self.character.DR}"
                )
            else:
                dr_tooltip = (
                    f"{stat_name} d{die_size} ÷ 2 = "
                    f"{self.character.DR}"
                )

            if self.character.selected_defense_stat_name:
                dr_tooltip += "\nChosen defense stat"
            else:
                dr_tooltip += "\nHighest stat"

            self.dr_box.setToolTip(dr_tooltip)


    def refresh_identity(self):
        name = self.character.name.strip()

        if not self.character_name_label.hasFocus():
            self.character_name_label.setText(name)

        self.character_name_label.setPlaceholderText("Unnamed Character")
            
        species_improvement = self.get_species_improvement()

        if species_improvement is None:
            self.species_label.hide()
            return

        species_name = species_improvement.choices.get("_species_name", "").strip()

        if species_name:
            if not self.species_label.hasFocus():
                self.species_label.setText(species_name)
        else:
            if not self.species_label.hasFocus():
                self.species_label.setText("")

        self.species_label.show()

    def update_character_name_from_ui(self):

        new_name = self.character_name_label.text().strip()

        if new_name == self.character.name:
            return

        self.character.name = new_name
        self.mark_dirty(auto_save=True)

    def update_species_name_from_ui(self):
        species_improvement = self.get_species_improvement()

        if species_improvement is None:
            return

        new_name = self.species_label.text().strip()

        old_name = species_improvement.choices.get(
            "_species_name",
            ""
        ).strip()

        if new_name == old_name:
            return

        species_improvement.choices["_species_name"] = new_name
        self.character.species_name = new_name

        self.mark_dirty(auto_save=True)

    # ============================================================
    # CHARACTER ACTIONS
    # ============================================================

    def level_up_from_ui(self):
        if self.is_campaign_character_for_tools():
            return
        if self.block_if_readonly():
            return
        
        old_level = self.character.progression.level
        new_level = old_level + 1

        if not ask_yes_no(
            self,
            "Level Up",
            (
                f"Level up from level {old_level} to level {new_level}?\n\n"
                "This will add:\n"
                "+2 IP\n"
                "+1 max AT\n"
                "+1 heart"
            ),
        ):
            return   

        self.character.grant_milestone(heal_new_heart=True)

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def open_ability_editor(self):
        if self.block_if_readonly():
            return

        allowed_array_ids = None

        if getattr(self, "active_character_template", False):
            allowed_array_ids = list(
                getattr(
                    self.character,
                    "creation_allowed_ability_array_ids",
                    [],
                )
            )

        dialog = AbilityEditorDialog(
            self.character,
            self,
            allowed_array_ids=allowed_array_ids,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.mark_dirty(auto_save=True)
            self.refresh_all()
                    
    def edit_name_from_ui(self):
        if self.is_readonly_character():
            return
        
        current = self.character.name.strip()

        name, ok = fantasy_text_input(
            self,
            "Edit Character Name",
            "Character name:",
            text=current,
            accept_text="Save",
        )

        if not ok:
            return

        self.character.name = name.strip()
        self.character.validate()

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def add_species_from_ui(self):
        if self.block_if_readonly():
            return

        # A campaign that does not require Species must not gain one via a
        # stale Tools action or an external shortcut. Existing selections can
        # still be edited through the visible Species field.
        if getattr(self.character, "creation_rules_active", False) and (
            getattr(self.character, "creation_species_mode", "normal") != "required"
        ):
            return

        self.choose_species_from_sheet()

    def choose_species_from_sheet(self):
        if self.block_if_readonly():
            return
        
        existing_species = self.get_species_improvement()

        if existing_species is not None:
            self.edit_species_from_sheet(existing_species)
            return

        # A campaign's optional/disabled species setting must be enforced in
        # the handler as well as in the Tools menu, even if the menu is stale.
        if getattr(self.character, "creation_rules_active", False) and (
            getattr(self.character, "creation_species_mode", "normal") != "required"
        ):
            return

        options = ImprovementSystem.get_species_options(self.character)

        if not options:
            QMessageBox.warning(
                self,
                "No Species Options",
                "No valid species improvements were found."
            )
            return

        picker = ImprovementPickerDialog(options, self)

        if picker.exec() != QDialog.DialogCode.Accepted:
            return

        selected_option = picker.selected_option

        if selected_option is None:
            return

        choices = {}
        required_choices = selected_option.get("requires_choices", [])

        if required_choices:
            choice_dialog = ChoiceInputDialog(
                required_choices,
                title=f"Choices for {selected_option['name']}",
                parent=self,
            )

            if choice_dialog.exec() == QDialog.DialogCode.Accepted:
                choices = choice_dialog.choices
            else:
                choices = {
                    choice_key: "Missing"
                    for choice_key in required_choices
                }

        species_name, ok = fantasy_text_input(
            self,
            "Species Name",
            "Write your species name:",
            text="",
            accept_text="Add",
        )

        if ok:
            species_name = species_name.strip()
        else:
            species_name = ""

        choices["_species_name"] = species_name


        success = ImprovementSystem.add_from_catalog(
            character=self.character,
            catalog_id=selected_option["catalog_id"],
            choices=choices,
            source="species",
        )

        if not success:
            QMessageBox.warning(
                self,
                "Species Failed",
                "Could not add species improvement."
            )
            return

        species_improvement = self.get_species_improvement()

        if species_improvement is not None:
            species_improvement.choices["_species_name"] = species_name


        self.character.species_name = species_name
        self.character.validate()

        if species_improvement is not None:
            species_improvement.choices["_species_name"] = species_name
            
        self.mark_dirty()
        self.refresh_all()

    def edit_species_from_sheet(self, species_improvement):
        option = ImprovementCatalogSystem.get_option(
            species_improvement.catalog_id
        )

        if option is None:
            QMessageBox.warning(
                self,
                "Species Error",
                "Could not find this species in the catalog."
            )
            return

        required_choices = option.get("requires_choices", [])

        
        species_name, ok = fantasy_text_input(
            self,
            "Edit Species Name",
            "Species name:",
            text=species_improvement.choices.get("_species_name", "").strip(),
            accept_text="Save",
        )

        if not ok:
            return
        species_name = species_name.strip()
        species_improvement.choices["_species_name"] = species_name
        self.character.species_name = species_name

        if required_choices:
            dialog = ChoiceInputDialog(
                required_choices,
                title=f"Edit {species_improvement.name}",
                parent=self,
                initial_choices=species_improvement.choices,
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                species_improvement.choices.update(dialog.choices)

        self.character.validate()
        species_improvement.choices["_species_name"] = species_name

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def grant_ip_from_ui(self):
        if self.is_campaign_character_for_tools():
            return
        if self.block_if_readonly():
            return
        
        
        if not ask_yes_no(
            self,
            "Grant IP",
            "Add 1 IP?",
            button_width=82,
            button_height=34,
            dialog_width=250,
        ):
            return

        self.character.grant_IP(1)

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def get_species_improvement(self):
        for improvement in self.character.improvements.list_of_taken_improvements:
            if improvement.source == "species":
                return improvement

        return None

    def character_has_species(self):
        return self.get_species_improvement() is not None
