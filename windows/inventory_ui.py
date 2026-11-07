from PySide6.QtCore import (
    Qt,
    QRect,
    QTimer,
)

from PySide6.QtGui import QTextDocument, QTextOption

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QDialog,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QMessageBox,
    QScrollArea,
)

from ui_widgets import NumericEntry

from ui_theme import (
    BLUE,
    set_themed_stylesheet,
    make_positive_button,
    make_negative_button,
    FANTASY_DIALOG_QSS,
    apply_fantasy_dialog_style,
)

from backend_2_1 import (
    InventorySystem,
)

from character_display_ui import (
    REGULAR_SHEET_HEIGHT,
)

from dialogs import (
    ask_yes_no,
)

from ui_widgets import BigPlusButton

class InventoryRow(QWidget):
    """
    Represents a single inventory item with quantity controls and
    remove/edit options.
    Displays the item inside a styled blue box with +/– buttons.
    """
    def __init__(self, item, remove_callback, increase_callback, decrease_callback):
        super().__init__()

        self.item = item
        self.remove_callback = remove_callback
        self.increase_callback = increase_callback
        self.decrease_callback = decrease_callback

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        self.main_box = QFrame()
        set_themed_stylesheet(self.main_box, f"""
            QFrame {{
                background-color: {BLUE};
                border: none;
                border-radius: 14px;
            }}
        """)
        self.main_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        box_layout = QVBoxLayout(self.main_box)
        box_layout.setContentsMargins(12, 4, 6, 4)
        box_layout.setSpacing(0)

        # Put the inventory header in its own widget so the arrow and item
        # name can stay vertically centered inside the coloured item box.
        # This matters most for collapsed rows whose box is taller than the
        # text, and for wrapped multi-line item names.
        self.header_widget = QWidget(self.main_box)
        self.header_widget.setStyleSheet("background: transparent;")

        top_row = QHBoxLayout(self.header_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(5)

        self.arrow_btn = QPushButton("▾" if item.expanded else "▸")
        self.arrow_btn.setFixedSize(18, 18)
        set_themed_stylesheet(self.arrow_btn, """
            QPushButton {
                background-color: transparent;
                border: none;
                font-weight: 900;
                font-size: 18px;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)
        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

        self.name_label = QLabel(item.name)

        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        
        set_themed_stylesheet(self.name_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 16px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        self.description_label = QLabel(str(item.description or "").strip())
        self.description_label.setTextFormat(Qt.TextFormat.PlainText)
        self.description_label.setVisible(bool(item.expanded and self.description_label.text()))
        self.description_label.setWordWrap(True)
        self.description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        set_themed_stylesheet(self.description_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)

        top_row.addWidget(self.arrow_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.remove_btn = QPushButton("×", self.main_box)
        self.remove_btn.setFixedSize(16, 16)
        set_themed_stylesheet(self.remove_btn, """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #aa0000;
            }
        """)
        self.remove_btn.setToolTip("Remove inventory item")
        self.remove_btn.clicked.connect(self.on_remove_clicked)
        # Place delete in the header layout instead of floating above the name.
        top_row.addWidget(self.remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        box_layout.addWidget(self.header_widget)
        box_layout.addWidget(self.description_label)

        self.quantity_box = QFrame()
        self.quantity_box.setFixedSize(34, 38)
        self.quantity_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        set_themed_stylesheet(self.quantity_box, f"""
            QFrame {{
                background-color: {BLUE};
                border: none;
                border-radius: 14px;
            }}
        """)

        quantity_layout = QVBoxLayout(self.quantity_box)
        quantity_layout.setContentsMargins(2, 2, 2, 2)
        quantity_layout.setSpacing(0)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(24, 10)
        self.plus_btn.clicked.connect(
            self.increase_quantity
        )

        self.quantity_label = QLabel(str(item.quantity))
        self.quantity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quantity_label.setFixedSize(24, 14)
        set_themed_stylesheet(self.quantity_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 14px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)

        self.minus_btn = QPushButton("-")
        self.minus_btn.setFixedSize(24, 10)
        self.minus_btn.clicked.connect(
            self.decrease_quantity
        )

        for btn in (self.plus_btn, self.minus_btn):
            set_themed_stylesheet(btn, f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }}

                QPushButton:hover {{
                    background-color: #d8eef8;
                }}
            """)

        quantity_layout.addWidget(self.plus_btn, 0, Qt.AlignmentFlag.AlignCenter)
        quantity_layout.addWidget(self.quantity_label, 0, Qt.AlignmentFlag.AlignCenter)
        quantity_layout.addWidget(self.minus_btn, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(self.main_box, 1)
        # Fixed-size quantity pill stays centered as text/description grows.
        outer.addWidget(self.quantity_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self.apply_expanded_geometry()

    def apply_expanded_geometry(self):
        """Keep collapsed Inventory rows genuinely compact."""
        # Restore the original compact height (38 logical px), without ever
        # stretching it when an item expands. The outer row centers it.
        # It is centered by the containing row, not resized to its height.
        self.header_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.quantity_box.setFixedSize(34, 38)
        self.plus_btn.setFixedSize(24, 10)
        self.quantity_label.setFixedSize(24, 14)
        self.minus_btn.setFixedSize(24, 10)

        self.quantity_box.updateGeometry()
        self.main_box.updateGeometry()
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # Delete is owned by the header layout, not manually positioned.


    def increase_quantity(self):
        old_quantity = self.item.quantity

        self.increase_callback(self.item)

        if self.item.quantity != old_quantity:
            self.quantity_label.setText(
                str(self.item.quantity)
            )


    def decrease_quantity(self):
        old_quantity = self.item.quantity

        self.decrease_callback(self.item)

        if self.item.quantity != old_quantity:
            self.quantity_label.setText(
                str(self.item.quantity)
            )

    def on_arrow_clicked(self):
        expanded = not self.item.expanded
        self.item.expanded = expanded

        window = self.window()
        
        self.description_label.setVisible(expanded)
        self.apply_expanded_geometry()

        self.arrow_btn.setText(
            "▾" if expanded else "▸"
        )

        self.description_label.updateGeometry()
        self.main_box.updateGeometry()
        self.updateGeometry()

        if self.parentWidget() is not None:
            self.parentWidget().updateGeometry()
            
        window = self.window()

        if hasattr(
            window,
            "refresh_inventory_scroll_geometry",
        ):
            QTimer.singleShot(
                0,
                window.refresh_inventory_scroll_geometry,
            )
    def on_remove_clicked(self):
        self.remove_callback(self.item)

    def mouseDoubleClickEvent(self, event):
        """
        Double-clicking the item body opens one editor for the complete item.

        The arrow, delete button, and quantity +/- controls keep their normal
        single-click behavior.
        """
        pos = event.position().toPoint()

        local_main_pos = self.main_box.mapFrom(
            self,
            pos,
        )

        if self.main_box.rect().contains(
            local_main_pos
        ):
            self.edit_item()
            return

        super().mouseDoubleClickEvent(
            event
        )

    def edit_item(self):
        if self.window().block_if_readonly():
            return

        dialog = InventoryItemDialog(
            parent=self,
            item=self.item,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        window = self.window()

        new_name = window.capitalize_first(
            dialog.item_name.strip()
        )

        new_description = window.capitalize_sentences(
            dialog.item_description.strip()
        )

        new_quantity = int(
            dialog.item_quantity
        )

        changed = (
            new_name != self.item.name
            or new_description != self.item.description
            or new_quantity != self.item.quantity
        )

        if not changed:
            return

        self.item.name = new_name
        self.item.description = new_description
        self.item.quantity = max(
            0,
            new_quantity,
        )

        window.mark_dirty(
            auto_save=True
        )
        window.refresh_all()

    @staticmethod
    def _wrapped_text_height(label, available_width):
        """Measure the text with the *displayed* font and real wrap width.

        QTextDocument supports both newlines and single words longer than the
        available width.  It is less prone to cutting off a last line than
        boundingRect(TextWordWrap) at Windows fractional display scaling.
        """
        text = label.text() or ""
        if not text:
            return 0
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(label.font())
        options = doc.defaultTextOption()
        options.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(options)
        doc.setPlainText(text)
        doc.setTextWidth(max(1, int(available_width)))
        # Reserve a little extra height for scaled fonts / layout rounding.
        return max(label.fontMetrics().height(), int(doc.size().height() + 0.9999) + 3)

    def required_height(self, total_width):
        """Fit the title, linked-note icons, delete button and description.

        The inventory row is the single sizing source for both the classic
        and redesigned sheet. Quantity is always a separate, fixed 34x38 pill
        centered by the row's outer horizontal layout, never expanded.
        """
        outer_layout = self.layout()
        outer_margins = outer_layout.contentsMargins()
        outer_spacing = outer_layout.spacing()
        main_width = max(
            1, int(total_width) - self.quantity_box.width()
            - outer_spacing - outer_margins.left() - outer_margins.right(),
        )
        box_layout = self.main_box.layout()
        box_margins = box_layout.contentsMargins()
        inner_width = max(1, main_width - box_margins.left() - box_margins.right())

        header_layout = self.header_widget.layout()
        header_margins = header_layout.contentsMargins()
        usable_width = max(1, inner_width - header_margins.left() - header_margins.right())
        fixed_controls = 0
        control_count = 0
        for index in range(header_layout.count()):
            widget = header_layout.itemAt(index).widget()
            if widget is None or widget is self.name_label:
                continue
            # Count explicit header controls even when the entire row is
            # temporarily hidden during a sheet refresh. Never use widget
            # .width() here: before first layout it can be a stale 640 px.
            fixed_controls += max(0, widget.minimumWidth(), widget.sizeHint().width())
            control_count += 1
        # The name label is always present, so there is a gap for each control.
        gaps = header_layout.spacing() * control_count
        name_width = max(1, usable_width - fixed_controls - gaps - 2)
        name_height = self._wrapped_text_height(self.name_label, name_width)
        minimum_header_height = max(
            (header_layout.itemAt(index).widget().sizeHint().height()
             for index in range(header_layout.count())
             if header_layout.itemAt(index).widget() is not None
             and header_layout.itemAt(index).widget() is not self.name_label),
            default=18,
        )

        self.name_label.setFixedWidth(name_width)
        self.name_label.setFixedHeight(max(18, name_height))
        self.header_widget.setFixedHeight(
            max(name_height, minimum_header_height)
            + header_margins.top() + header_margins.bottom()
        )

        expanded = bool(self.item.expanded and self.description_label.text())
        # isVisible() is false when the whole screen is hidden during a
        # refresh; use the item model instead, so no text is cut off.
        self.description_label.setVisible(expanded)
        desc_height = 0
        if expanded:
            desc_height = self._wrapped_text_height(self.description_label, inner_width) + 3
            self.description_label.setFixedWidth(inner_width)
            self.description_label.setFixedHeight(desc_height)
        else:
            # Undo *both* the old height and Qt's text-driven size hint.
            self.description_label.setFixedHeight(0)

        main_height = (box_margins.top() + self.header_widget.height()
                       + (box_layout.spacing() + desc_height if expanded else 0)
                       + box_margins.bottom())
        return max(self.quantity_box.height(), main_height)

class AutoGrowTextDialog(QDialog): # called only for inventory description.
    """
    A dialog with a text box that expands as the user types.
    Used for writing longer notes or descriptions.
    """
    def __init__(self, title, label, text="", parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        set_themed_stylesheet(
            self,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title_label = QLabel(label)
        layout.addWidget(title_label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_edit.setMinimumHeight(60)
        self.text_edit.setMaximumHeight(260)
        self.text_edit.textChanged.connect(self.auto_resize)

        layout.addWidget(self.text_edit)

        button_row = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        make_negative_button(cancel_btn)
        
        save_btn = QPushButton("Save")
        make_positive_button(save_btn)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)

        button_row.addWidget(cancel_btn)
        button_row.addStretch()
        button_row.addWidget(save_btn)

        layout.addLayout(button_row)

        self.auto_resize()
        apply_fantasy_dialog_style(self)

    def auto_resize(self):
        doc_height = int(self.text_edit.document().size().height()) + 20
        new_height = max(60, min(260, doc_height))

        self.text_edit.setFixedHeight(new_height)
        self.adjustSize()

    def text(self):
        return self.text_edit.toPlainText()

class InventoryEditDialog(QDialog):
    def __init__(
        self,
        title,
        field_label,
        text="",
        multiline=False,
        parent=None,
    ):
        super().__init__(parent)

        self.multiline = multiline
        self.result_text = text

        self.setWindowTitle(title)

        if multiline:
            self.setFixedSize(500, 210)
        else:
            self.setFixedSize(500, 145)

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 800;
                color: #25190f;
            }}

            QLineEdit,
            QTextEdit {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 6px;
                font-size: 14px;
                font-weight: 700;
                color: #25190f;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        # --------------------------------------------------------
        # Field row
        # --------------------------------------------------------

        field_row = QHBoxLayout()
        field_row.setSpacing(14)

        label = QLabel(field_label)
        label.setFixedWidth(135)
        label.setWordWrap(True)
        label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )

        if multiline:
            self.input = QTextEdit()
            self.input.setPlainText(text)
            self.input.setFixedHeight(85)
        else:
            self.input = QLineEdit()
            self.input.setText(text)
            self.input.setFixedHeight(40)
            self.input.selectAll()

        field_row.addWidget(label)
        field_row.addWidget(self.input, 1)

        layout.addLayout(field_row)

        layout.addStretch()

        # --------------------------------------------------------
        # Buttons
        # --------------------------------------------------------

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)

        cancel_btn = QPushButton("Cancel")
        make_negative_button(cancel_btn)
        cancel_btn.setFixedSize(92, 42)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        make_positive_button(save_btn)
        save_btn.setFixedSize(92, 42)
        save_btn.setDefault(True)
        save_btn.setAutoDefault(True)
        cancel_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.accept_text)

        button_row.addWidget(cancel_btn)
        button_row.addStretch()
        button_row.addWidget(save_btn)

        layout.addLayout(button_row)

        self.input.setFocus()
        apply_fantasy_dialog_style(self)

    def accept_text(self):
        if self.multiline:
            text = self.input.toPlainText().strip()
        else:
            text = self.input.text().strip()

        if not text:
            QMessageBox.warning(
                self,
                "Missing Text",
                "This field cannot be empty."
            )
            return

        self.result_text = text
        self.accept()

        
class InventoryItemDialog(QDialog):
    """
    Dialog for adding a new inventory item with name, quantity, and description.
    Used when clicking the “+” button in the inventory section.
    """
    def __init__(
        self,
        parent=None,
        item=None,
    ):
        super().__init__(parent)

        self.item = item
        self.editing_existing_item = (
            item is not None
        )

        self.item_name = (
            str(item.name)
            if item is not None
            else ""
        )
        self.item_description = (
            str(item.description)
            if item is not None
            else ""
        )
        self.item_quantity = (
            int(item.quantity)
            if item is not None
            else 1
        )

        self.setWindowTitle(
            "Edit Inventory Item"
            if self.editing_existing_item
            else "Add Inventory Item"
        )
        self.setFixedSize(460, 300)

        set_themed_stylesheet(self, f"""
            QDialog {{
                background-color: #fffdf7;
            }}

            QLabel {{
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 800;
                color: #25190f;
            }}

            QLineEdit, QTextEdit, QSpinBox {{
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 6px;
                font-size: 14px;
                font-weight: 700;
                color: #25190f;
            }}

            QPushButton {{
                background-color: {BLUE};
                border: 1px solid #c79a3b;
                border-radius: 14px;
                padding: 8px 18px;
                font-size: 15px;
                font-weight: 800;
            }}

            QPushButton:hover {{
                background-color: #d8eef8;
            }}

            QPushButton#PositiveButton {{
                background-color: #d8edf7;
                border: 1px solid #c79a3b;
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 14px;
                font-weight: 800;
            }}

            QPushButton#PositiveButton:hover {{
                background-color: #e8f5fb;
            }}

            QPushButton#NegativeButton {{
                background-color: #fffdf7;
                border: 1px solid #c79a3b;
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 14px;
                font-weight: 800;
            }}

            QPushButton#NegativeButton:hover {{
                background-color: #fff4df;
            }}
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel(
            "Edit Inventory Item"
            if self.editing_existing_item
            else "Add Inventory Item"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(title, """
            font-size: 18px;
            font-weight: 900;
        """)
        layout.addWidget(title)

        name_row = QHBoxLayout()
        name_label = QLabel("Name")
        name_label.setFixedWidth(90)

        self.name_input = QLineEdit()
        self.name_input.setText(
            self.item_name
        )
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_input, 1)
        layout.addLayout(name_row)

        quantity_row = QHBoxLayout()
        quantity_label = QLabel("Quantity")
        quantity_label.setFixedWidth(90)

        self.quantity_input = NumericEntry()
        self.quantity_input.setMinimum(0)
        self.quantity_input.setMaximum(999)
        self.quantity_input.setValue(
            self.item_quantity
        )

        # Hide broken native arrows. Quantity can be typed here,
        # and changed later with the + / - buttons on the item row.
        self.quantity_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        quantity_row.addWidget(quantity_label)
        quantity_row.addWidget(self.quantity_input, 1)
        layout.addLayout(quantity_row)

        description_label = QLabel("Description")
        layout.addWidget(description_label)

        self.description_input = QTextEdit()
        self.description_input.setPlainText(
            self.item_description
        )
        self.description_input.setPlaceholderText("Write one sentence about this item.")
        self.description_input.setFixedHeight(80)
        layout.addWidget(self.description_input)

        button_row = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        make_negative_button(self.cancel_btn)
        
        self.add_btn = QPushButton(
            "Save"
            if self.editing_existing_item
            else "Add"
        )
        make_positive_button(self.add_btn)

        self.cancel_btn.clicked.connect(self.reject)
        self.add_btn.clicked.connect(self.accept_item)

        button_row.addWidget(self.cancel_btn)
        button_row.addStretch()
        button_row.addWidget(self.add_btn)

        layout.addLayout(button_row)

        apply_fantasy_dialog_style(self)

        # QSpinBox text can be vertically clipped by the shared fantasy
        # dialog padding on some DPI/font combinations. Give this field
        # a stable height and use smaller vertical padding.
        self.quantity_input.setFixedHeight(40)
        set_themed_stylesheet(
            self.quantity_input,
            """
            QSpinBox {
                background-color: #fffaf0;
                border: 1px solid #d9bd82;
                border-radius: 10px;
                padding: 2px 8px 4px 8px;
                font-size: 14px;
                font-weight: 700;
                color: #25190f;
            }

            QSpinBox:focus {
                border: 1px solid #a87824;
                background-color: #fffdf7;
            }
            """,
        )

    def accept_item(self):
        name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()
        quantity = int(self.quantity_input.value())

        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter an item name.")
            return

        if not description:
            QMessageBox.warning(
                self,
                "Missing Description",
                "Please enter a short item description."
            )
            return

        self.item_name = name
        self.item_description = description
        self.item_quantity = quantity

        self.accept()

class InventoryMixin:
    def build_inventory_column(self, main_layout):
        inv_frame = QFrame()
        self.inventory_frame = inv_frame
        inv_frame.setObjectName("InventoryFrame")
        inv_frame.setFixedHeight(REGULAR_SHEET_HEIGHT)

        inv_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        set_themed_stylesheet(inv_frame, """
            QFrame#InventoryFrame {
                background-color: white;
                border: 3px solid black;
                border-radius: 14px;
            }
        """)

        inv_layout = QVBoxLayout(inv_frame)
        inv_layout.setContentsMargins(10, 10, 10, 10)
        inv_layout.setSpacing(8)

        # ========================================================
        # TITLE
        # ========================================================

        inv_title = QLabel("Inventory")
        inv_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        set_themed_stylesheet(inv_title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 22px;
                font-weight: 800;
                color: black;
            }
        """)

        inv_layout.addWidget(inv_title)

        # ========================================================
        # SCROLLABLE INVENTORY LIST
        # ========================================================

        self.inventory_scroll = QScrollArea()
        self.inventory_scroll.setWidgetResizable(False)
        self.inventory_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.inventory_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Keep wheel/trackpad scrolling, but do not display the intrusive
        # scrollbar or let its changing width move the item cards.
        self.inventory_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        set_themed_stylesheet(self.inventory_scroll, """
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background-color: #9fcfe3;
                border-radius: 5px;
                min-height: 24px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.inventory_list_widget = QWidget()

        self.inventory_list_layout = QVBoxLayout(
            self.inventory_list_widget
        )

        self.inventory_list_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.inventory_list_layout.setSpacing(8)

        self.inventory_scroll.setWidget(
            self.inventory_list_widget
        )

        inv_layout.addWidget(
            self.inventory_scroll
        )

        # ========================================================
        # ADD BUTTON — ALWAYS OUTSIDE THE SCROLLER
        # ========================================================

        self.add_item_btn = BigPlusButton("+")
        self.add_item_btn.clicked.connect(
            self.add_inventory_item_from_ui
        )

        inv_layout.addWidget(self.add_item_btn)

        inv_layout.addStretch()

        main_layout.addWidget(
            inv_frame,
            3,
            Qt.AlignmentFlag.AlignTop,
        )

    def refresh_inventory(self):
        self.clear_layout(self.inventory_list_layout)

        for item in self.character.inventory.list_of_items:
            row = InventoryRow(
                item,
                self.confirm_remove_inventory_item,
                self.increase_inventory_item,
                self.decrease_inventory_item,
            )
            self.inventory_list_layout.addWidget(row)

        QTimer.singleShot(
            0,
            self.refresh_inventory_scroll_geometry,
        )

    def refresh_inventory_scroll_geometry(self):
        if not hasattr(self, "inventory_scroll"):
            return

        layout = self.inventory_list_layout
        item_count = layout.count()

        if item_count == 0:
            self.inventory_scroll.hide()
            self.inventory_scroll.setFixedHeight(0)
            return

        self.inventory_scroll.show()

        viewport_width = self.inventory_scroll.viewport().width()

        if viewport_width <= 0:
            viewport_width = self.inventory_scroll.width()

        content_width = max(
            1,
            viewport_width,
        )

        self.inventory_list_widget.setFixedWidth(
            content_width
        )

        content_height = 0
        widget_count = 0

        for index in range(item_count):
            item = layout.itemAt(index)
            widget = item.widget()

            if widget is None:
                continue

            widget.setFixedWidth(content_width)

            row_height = (
                widget.required_height(
                    content_width
                )
            )

            widget.setFixedHeight(
                row_height
            )

            content_height += row_height
            widget_count += 1

        if widget_count > 1:
            content_height += (
                layout.spacing()
                * (widget_count - 1)
            )

        margins = layout.contentsMargins()

        content_height += (
            margins.top()
            + margins.bottom()
        )

        self.inventory_list_widget.setFixedHeight(
            content_height
        )

        # ========================================================
        # MAXIMUM AVAILABLE INVENTORY HEIGHT
        # ========================================================

        frame = self.inventory_scroll.parentWidget()
        parent_layout = frame.layout()

        frame_height = frame.height()

        frame_margins = (
            parent_layout.contentsMargins()
        )

        spacing = parent_layout.spacing()

        # Inventory title is first item.
        title_height = (
            parent_layout
            .itemAt(0)
            .sizeHint()
            .height()
        )

        add_button_height = (
            self.add_item_btn.sizeHint().height()
        )

        # Small space between list and + button.
        scroll_bottom_gap = 10

        maximum_height = (
            frame_height
            - frame_margins.top()
            - frame_margins.bottom()
            - title_height
            - add_button_height
            - (spacing * 2)
            - scroll_bottom_gap
        )

        maximum_height = max(
            0,
            maximum_height,
        )

        visible_height = min(
            content_height,
            maximum_height,
        )
        self.inventory_scroll.setFixedHeight(visible_height)
        # Overflow is still scrollable by mouse wheel / trackpad. Hiding
        # the painted scrollbar does not disable its internal range.
        self.inventory_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    # ============================================================
    # INVENTORY ACTIONS
    # ============================================================

    def add_inventory_item_from_ui(self):
        if self.block_if_readonly():
            return
        
        dialog = InventoryItemDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = self.capitalize_first(
            dialog.item_name.strip()
        )

        description = self.capitalize_first(
            dialog.item_description.strip()
        )

        InventorySystem.add_item(
            self.character,
            name=name,
            description=description,
            quantity=dialog.item_quantity,
        )

        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def confirm_remove_inventory_item(self, item):
        if self.is_readonly_character():
            return
        
        if not ask_yes_no(
            self,
            "Remove Item",
            f"Remove {item.name}?"
        ):
            return

        InventorySystem.remove_item(self.character, item.id)
        self.mark_dirty(auto_save=True)
        self.refresh_all()

    def increase_inventory_item(self, item):
        if self.block_if_readonly():
            return
        
        InventorySystem.adjust_quantity(
            self.character,
            item.id,
            1,
        )

        self.mark_dirty()

    def decrease_inventory_item(self, item):
        if self.block_if_readonly():
            return
        if item.quantity <= 0:
            return

        InventorySystem.adjust_quantity(
            self.character,
            item.id,
            -1,
        )

        self.mark_dirty()
