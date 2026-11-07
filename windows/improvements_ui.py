from copy import deepcopy
from html import escape as escape_html
from PySide6.QtCore import (
    Qt,
    QTimer,
    QEvent,
    QPointF,
)
from PySide6.QtGui import QPainter, QColor

from PySide6.QtWidgets import (
    QApplication,
    QStylePainter,
    QStyleOptionButton,
    QStyle,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QSizePolicy,
    QLayout,
    QDialog,
    QComboBox,
    QMessageBox,
)

from backend_2_1 import (
    Improvement,
    ImprovementSystem,
    ImprovementCatalogSystem,
    STAT_NAMES,
    StatSystem,
    Character,
    HPSystem,
    ATSystem,
)

from character_display_ui import (
    REGULAR_SHEET_HEIGHT,
)

from ui_widgets import (
    AutoWrapLabel,
    BigPlusButton,
    IPLabel,
    SmallTopBox,
)

from ui_theme import (
    BLUE,
    set_themed_stylesheet,
    make_positive_button,
    make_negative_button,
    FANTASY_DIALOG_QSS,
    theme_color,
)
import ui_theme as ui_theme_module

from character_API import (
    IMPROVEMENT_CATALOG,
)

ABILITY_ACCENTS = {
    "agility": "#6F8F2C",
    "finesse": "#356FA8",
    "instinct": "#6B55A6",
    "knowledge": "#B17828",
    "presence": "#2F8792",
    "strength": "#A8453C",
}


class LineRemoveButton(QPushButton):
    """Keep the small removal glyph aligned to the label's first text line."""
    def __init__(self, label):
        super().__init__("×")
        self.target_label = label
        self.setFixedSize(18, 22)
        self.setToolTip("Remove")

    def paintEvent(self, event):
        # Preserve the standard QPushButton glyph, font, and hover styling.
        # Only move its normal 15px drawing rectangle to the text line.
        label = self.target_label
        metrics = label.fontMetrics()
        top = label.mapTo(self.parentWidget(), label.contentsRect().topLeft()).y() - self.y()
        center = top + metrics.ascent() - metrics.xHeight() / 2
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.rect.setTop(round(center - 7.5))
        option.rect.setHeight(15)
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        painter.end()


class ImprovementBullet(QWidget):
    """A bullet fixed to the first text line, independent of font baselines."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(13, 22)
        self.target_label = None

    def set_target(self, label):
        self.target_label = label
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f2eee7" if ui_theme_module.CURRENT_THEME == "dark" else "#222222"))
        center_y = 10
        if self.target_label is not None:
            label = self.target_label
            label_top = label.mapTo(self.parentWidget(), label.contentsRect().topLeft()).y()
            metrics = label.fontMetrics()
            center_y = max(4, min(18, label_top - self.y()
                                   + metrics.ascent() - metrics.xHeight() / 2))
        painter.drawEllipse(QPointF(5, center_y), 2, 2)
        painter.end()


MERGED_EMPOWERMENTS = {
    "additional_attuned_land",
    "school_savant",
    "hobbled",
    "drop_item",
    "drooling",
    "gifted",
    "well_trained",
    "animist",
    "thing_talker",
}

from dialogs import (
    ChoiceInputDialog,
    CustomImprovementDialog,
    ask_yes_no,
    ImprovementPickerDialog,
    apply_rule_glossary_html,
    show_rule_glossary_tooltip,
    hide_rule_glossary_tooltip,
    
)

class GlossaryAutoWrapLabel(AutoWrapLabel):
    """
    Purchased-Improvement description label with invisible glossary links.
    """

    def __init__(
        self,
        source_text="",
        parent=None,
    ):
        super().__init__(
            "",
            parent,
        )

        self._glossary_source_text = str(
            source_text or ""
        )

        self.setTextFormat(
            Qt.TextFormat.RichText
        )

        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )

        self.setOpenExternalLinks(
            False
        )

        self.linkHovered.connect(
            self._on_glossary_link_hovered
        )

        self.set_glossary_text(
            self._glossary_source_text
        )

    def heightForWidth(self, width):
        # AutoWrapLabel measures raw HTML tags as visible text, making rich-text
        # Improvement descriptions artificially tall. Use QLabel's native
        # rich-text layout measurement instead; this changes spacing only.
        return QLabel.heightForWidth(self, width)

    def set_glossary_text(
        self,
        source_text,
    ):
        self._glossary_source_text = str(
            source_text or ""
        )

        self.setText(
            apply_rule_glossary_html(
                self._glossary_source_text,
                link_color=("#f2eee7" if ui_theme_module.CURRENT_THEME == "dark"
                            else theme_color("fantasy_text")),
            )
        )

    def _on_glossary_link_hovered(
        self,
        anchor,
    ):
        if anchor:
            show_rule_glossary_tooltip(
                anchor,
                self._glossary_source_text,
            )
        else:
            hide_rule_glossary_tooltip()

    def leaveEvent(
        self,
        event,
    ):
        hide_rule_glossary_tooltip()

        super().leaveEvent(
            event
        )

class ImprovementRow(QWidget):
    """
    Displays one purchased improvement with expand/collapse behavior.
    Shows description, empowerments, choices, and remove/edit controls.
    """
    def __init__(
        self,
        character,
        improvement,
        remove_callback,
        edit_callback=None,
        remove_empowerment_callback=None
    ):
        super().__init__()
        self.character = character
        self.improvement = improvement
        self.remove_callback = remove_callback
        self.edit_callback = edit_callback
        self.remove_empowerment_callback = remove_empowerment_callback
        self.display = ImprovementSystem.build_improvement_display(
            character,
            improvement,
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum
        )

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
            QSizePolicy.Policy.Minimum
        )

        box_layout = QVBoxLayout(self.main_box)
        box_layout.setContentsMargins(12, 4, 12, 4)
        box_layout.setSpacing(0)
        # The list gives every row a minimum height for its cost circle.
        # When collapsed, vertically center the ONLY visible header in that
        # height. Expanded rows instead keep the header and body top-aligned.
        box_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop if improvement.expanded
            else Qt.AlignmentFlag.AlignVCenter
        )

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.arrow_btn = QPushButton("▾" if improvement.expanded else "▸")
        self.arrow_btn.setFixedSize(22, 22)
        set_themed_stylesheet(self.arrow_btn, """
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 17px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #2f5f91;
            }
        """)
        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

        self.name_label = QLabel(self.display["name"])


        # Allow all long improvement names to wrap instead of being cut off.
        self.name_label.setWordWrap(True)
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred
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

        top_row.addWidget(self.arrow_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)
        top_row.addSpacing(22)
        top_row.addStretch()

        # QBoxLayout.addLayout accepts only (layout, stretch), not alignment.
        # The parent box_layout already centers its contents in collapsed mode.
        box_layout.addLayout(top_row, 0)

        self.remove_btn = QPushButton("×", self.main_box)
        self.remove_btn.setFixedSize(20, 20)
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
        self.remove_btn.clicked.connect(self.on_remove_clicked)
        self.remove_btn.raise_()

        if improvement.expanded:
            # Backend supplies the complete API-authored summary. The UI
            # must not remove, paraphrase or append Improvement prose.
            summary = self.display.get("summary", "").strip()
            if summary:
                summary_label = GlossaryAutoWrapLabel(summary)
                summary_label.setTextFormat(Qt.TextFormat.RichText)
                summary_label.setWordWrap(True)
                summary_label.setMinimumWidth(0)
                summary_label.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
                summary_label.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Maximum,
                )
                set_themed_stylesheet(summary_label, """
                    QLabel {
                        border: none;
                        background: transparent;
                        font-size: 12px;
                        color: black;
                        padding: 0px;
                        margin: 0px;
                    }
                """)
                box_layout.addWidget(
                    summary_label, 0, Qt.AlignmentFlag.AlignTop
                )

            if improvement.catalog_id == "communion_of_whispers":
                self.add_merged_empowerment_remove_row(
                    box_layout,
                    improvement,
                    "animist",
                    "Animist",
                    remove_empowerment_callback,
                )

            if improvement.catalog_id == "wild_empathy":
                self.add_merged_empowerment_remove_row(
                    box_layout,
                    improvement,
                    "thing_talker",
                    "Thing Talker",
                    remove_empowerment_callback,
                )
                
            if (
                improvement.catalog_id == "sneak_attack"
                and not improvement.choices.get("_sneak_attack_nore_created")
            ):
                self.add_sneak_attack_effects(
                    box_layout,
                    improvement,
                    remove_empowerment_callback,
                )

            elif (
                improvement.catalog_id == "animal_buddy"
                or improvement.choices
                or improvement.catalog_id == "spellcasting"
            ):
                self.add_choices_section(
                    box_layout,
                    improvement,
                    remove_empowerment_callback,
                )
            if improvement.catalog_id == "animal_buddy":
                self.add_animal_buddy_empowerments(
                    box_layout,
                    improvement,
                    remove_empowerment_callback,
                )
            # ------------------------------------------------------------
            # Extra purchased levels of repeatable-scaling base improvements
            # such as Berserker and Hearty.
            # ------------------------------------------------------------

            option = ImprovementCatalogSystem.get_option(
                improvement.catalog_id
            )

            if (
                option is not None
                and option.get("purchase_rule") == "repeatable_scaling"
            ):
                times_taken = getattr(
                    improvement,
                    "times_taken",
                    1,
                )

                if times_taken > 1:
                    scaling_title = QLabel("Improvements")
                    set_themed_stylesheet(scaling_title, """
                        QLabel {
                            border: none;
                            background: transparent;
                            font-size: 13px;
                            font-weight: 900;
                            color: black;
                            padding-top: 1px;
                        }
                    """)
                    box_layout.addWidget(scaling_title)

                    value_key = option.get("value_key")
                    base_value = int(option.get("base_value", 1))
                    increase_by = int(option.get("increase_by", 1))

                    for rank in range(2, times_taken + 1):
                        row = QHBoxLayout()
                        row.setContentsMargins(10, 0, 0, 0)
                        row.setSpacing(4)

                        value = (
                            base_value
                            + ((rank - 1) * increase_by)
                        )

                        # Friendly text for the known scaling value.
                        if value_key == "extra_at_from_damage":
                            value_text = (
                                f"+{value} additional AT"
                            )

                        elif value_key == "hp_per_heart":
                            value_text = (
                                f"{value} HP per Heart"
                            )

                        else:
                            value_text = str(value)

                        bullet = ImprovementBullet()
                        row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
                        label = QLabel(
                            f"{improvement.name} ⇒ {value_text}"
                        )
                        label.setWordWrap(True)
                        label.setProperty("compact_improvement_line", True)
                        set_themed_stylesheet(label, """
                            QLabel {
                                border: none;
                                background: transparent;
                                font-size: 12px;
                                font-weight: 800;
                                color: #222222;
                            }
                        """)

                        row.addWidget(label, 1)
                        bullet.set_target(label)

                        # Only the highest currently owned level may be removed.
                        if rank == times_taken:
                            remove_level_btn = QPushButton("×")
                            remove_level_btn.setFixedSize(18, 18)
                            set_themed_stylesheet(remove_level_btn, """
                                QPushButton {
                                    background: transparent;
                                    border: none;
                                    font-size: 14px;
                                    font-weight: 900;
                                    color: black;
                                }

                                QPushButton:hover {
                                    color: #aa0000;
                                }
                            """)

                            remove_level_btn.clicked.connect(
                                lambda checked=False, imp=improvement:
                                    self.window().confirm_remove_scaling_level(
                                        imp
                                    )
                            )

                            row.addWidget(
                                remove_level_btn,
                                0,
                                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                            )

                        box_layout.addLayout(row)
            
            visible_empowerments = [
                e for e in improvement.empowerments
                if (
                    e.catalog_id != "additional_attuned_land"
                    and e.group_id != "school_savant"
                    and e.catalog_id not in MERGED_EMPOWERMENTS
                    and e.group_id not in MERGED_EMPOWERMENTS
                    and improvement.catalog_id != "animal_buddy"
                )
            ]

            if visible_empowerments:
                emp_title = QLabel("Empowerments")
                emp_title.setContentsMargins(0, 0, 0, 0)
                set_themed_stylesheet(emp_title, """
                    QLabel {
                        border: none;
                        background: transparent;
                        font-size: 13px;
                        font-weight: 900;
                        color: black;
                        padding-top: 0px;
                        margin: 0px;
                    }
                """)
                box_layout.addWidget(emp_title)

                for empowerment in visible_empowerments:
                    emp_row = QHBoxLayout()
                    emp_row.setContentsMargins(10, 0, 2, 0)
                    emp_row.setSpacing(0)
                    emp_row.setAlignment(Qt.AlignmentFlag.AlignTop)

                    display_name = empowerment.name.replace("->", "⇒")

                    bullet = ImprovementBullet()
                    emp_row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
                    emp_label = QLabel(display_name)
                    emp_label.setProperty("compact_improvement_line", True)
                    emp_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    emp_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    emp_label.setWordWrap(True)
                    set_themed_stylesheet(emp_label, """
                        QLabel {
                            border: none;
                            background: transparent;
                            font-size: 12px;
                            font-weight: 800;
                            color: #222222;
                        }
                    """)
                    emp_row.addWidget(emp_label, 1)
                    bullet.set_target(emp_label)
                    
                    # Only the highest owned level of an ordered/scaling
                    # empowerment group may be removed.
                    can_remove = self.can_remove_empowerment(empowerment)

                    if can_remove and remove_empowerment_callback is not None:
                        emp_remove_btn = LineRemoveButton(emp_label)
                        set_themed_stylesheet(emp_remove_btn, """
                            QPushButton {
                                background: transparent;
                                border: none;
                                font-size: 14px;
                                font-weight: 900;
                                color: black;
                                padding: 0px;
                                margin: 0px;
                            }

                            QPushButton:hover {
                                color: #aa0000;
                            }
                        """)

                        emp_remove_btn.clicked.connect(
                            lambda checked=False, e=empowerment:
                                remove_empowerment_callback(improvement, e)
                        )

                        emp_row.addWidget(emp_remove_btn, 0, Qt.AlignmentFlag.AlignTop)

                    box_layout.addLayout(emp_row)
                    
        if improvement.source == "species":
            cost_text = "S"
        else:
            cost_text = str(improvement.total_cost())

        self.count_box = QLabel(cost_text)
        self.count_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_box.setFixedSize(34, 34)
        set_themed_stylesheet(self.count_box, f"""
            QLabel {{
                background-color: {BLUE};
                border: none;
                border-radius: 17px;
                font-size: 14px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }}
        """)

        outer.addWidget(self.main_box, 1)
        outer.addWidget(self.count_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.main_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

    def format_choices(self, choices, improvement=None):
        if (
            improvement is not None
            and improvement.catalog_id == "born_of_soil"
        ):
            lands = []

            primary_land = choices.get("attuned_land")
            if primary_land and primary_land != "Missing":
                lands.append(self.pretty_value(primary_land))

            for empowerment in improvement.empowerments:
                if empowerment.catalog_id == "additional_attuned_land":
                    extra_land = empowerment.choices.get("attuned_land")
                    if extra_land and extra_land != "Missing":
                        lands.append(self.pretty_value(extra_land))

            lands_text = ", ".join(lands) if lands else "Missing"

            raw_tell = choices.get("tell")
            tell = (
                self.pretty_value(raw_tell)
                if raw_tell and raw_tell != "Missing"
                else "Missing Tell"
            )

            return f"Lands: {lands_text}  |  Tell: {tell}"


        if (
            improvement is not None
            and improvement.catalog_id == "spellcasting"
        ):
            schools = []

            primary_school = choices.get("magic_school")
            primary_description = choices.get("magic_school_description")

            if primary_school and primary_school != "Missing":
                school_text = self.pretty_value(primary_school)

                schools.append(school_text)

            for empowerment in improvement.empowerments:
                if empowerment.group_id == "school_savant":
                    extra_school = empowerment.choices.get("magic_school")
                    extra_description = empowerment.choices.get("magic_school_description")

                    if extra_school and extra_school != "Missing":
                        school_text = self.pretty_value(extra_school)

                        schools.append(school_text)

            schools_text = "\n".join(f"• {school}" for school in schools) if schools else "Missing"

            return f"Schools:\n{schools_text}"

        pretty = {
            "buddy_name": "Name",
            "buddy_stat_d6": "d6",
            "buddy_stat_d8_a": "d8",
            "buddy_stat_d8_b": "d8",
            "buddy_stat_d10": "d10",
            "buddy_perk": "Perk",
            "magic_school": "School",
            "magic_school_description": "School Description",
            "specific_magic_effect": "Effect",
            "stat_name": "Stat",
            "attuned_land": "Land",
            "tell": "Tell",
            "deity_name": "Deity",
            "deity_domain": "Domain",
            "skill_name": "Skill",
            "skill_description": "Description",
            "artificer_item_description": "Item",
        }

        lines = []

        if "buddy_name" in choices:
            raw_name = choices.get("buddy_name")
            name = (
                self.pretty_value(raw_name)
                if raw_name and raw_name != "Missing"
                else "Unnamed Buddy"
            )

            perks = []

            base_perk = choices.get("buddy_perk")
            if base_perk and base_perk != "Missing":
                perks.append(self.pretty_value(base_perk))

            buddy_bonuses = {
                stat_name: 0
                for stat_name in STAT_NAMES
            }

            if improvement is not None:
                for empowerment in improvement.empowerments:
                    if empowerment.catalog_id == "gifted":
                        extra_perk = empowerment.choices.get("buddy_perk")

                        if extra_perk and extra_perk != "Missing":
                            perks.append(self.pretty_value(extra_perk))

                    elif empowerment.catalog_id == "well_trained":
                        stat_name = empowerment.choices.get(
                            "buddy_training_stat"
                        )

                        if stat_name in buddy_bonuses:
                            buddy_bonuses[stat_name] += 1

            perks_text = ", ".join(perks) if perks else "Missing"

            lines.append(
                f"Name: {name}\n"
                f"Perk: {perks_text}"
            )

            buddy_dice = {
                stat_name: 4
                for stat_name in STAT_NAMES
            }

            assigned_dice = [
                (choices.get("buddy_stat_d10"), 10),
                (choices.get("buddy_stat_d8_a"), 8),
                (choices.get("buddy_stat_d8_b"), 8),
                (choices.get("buddy_stat_d6"), 6),
            ]

            for stat_name, die_size in assigned_dice:
                if (
                    stat_name
                    and stat_name != "Missing"
                    and stat_name in buddy_dice
                ):
                    buddy_dice[stat_name] = die_size

            sorted_stats = sorted(
                STAT_NAMES,
                key=lambda stat_name: (
                    -buddy_dice[stat_name],
                    -buddy_bonuses.get(stat_name, 0),
                    stat_name,
                ),
            )

            stat_texts = []

            for stat_name in sorted_stats:
                die_size = buddy_dice[stat_name]
                bonus = buddy_bonuses.get(stat_name, 0)

                bonus_text = f"+{bonus}" if bonus > 0 else ""

                stat_texts.append(
                    f"{self.pretty_value(stat_name)} "
                    f"d{die_size}{bonus_text}"
                )

            # Add the title BEFORE the stat rows.
            lines.append("Stats:")

            # Two stats per row.
            for i in range(0, len(stat_texts), 2):
                lines.append(
                    "  |  ".join(stat_texts[i:i + 2])
                )

            return "\n".join(lines)
            

        pairs = []

        for key, value in choices.items():
            if str(key).startswith("_"):
                continue
            readable_key = pretty.get(key, key.replace("_", " ").title())
            readable_value = self.pretty_value(value)
            pairs.append(f"{readable_key}: {readable_value}")

        for i in range(0, len(pairs), 2):
            if i + 1 < len(pairs):
                lines.append(f"{pairs[i]}  |  {pairs[i + 1]}")
            else:
                lines.append(pairs[i])

        return "\n".join(lines)

    def pretty_value(self, value):
        if value is None or value == "":
            return "Missing"

        return str(value).replace("_", " ").title()

    def on_remove_clicked(self):
        self.remove_callback(self.improvement)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self.remove_btn.move(
            self.main_box.width() - self.remove_btn.width() - 6,
            6
        )

    def on_arrow_clicked(self):
        self.improvement.expanded = not self.improvement.expanded

        window = self.window()

        # Expanding one card should not destroy/recreate every other card:
        # that causes the entire two-column sheet to jump and briefly blank.
        if hasattr(window, "replace_expanded_improvement_row"):
            window.replace_expanded_improvement_row(self)
        elif hasattr(window, "refresh_improvements"):
            window.refresh_improvements()

    def mouseDoubleClickEvent(self, event):
        if self.edit_callback is None:
            return

        pos = event.position().toPoint()

        local_name_pos = self.name_label.mapFrom(self, pos)

        if self.name_label.rect().contains(local_name_pos):
            self.edit_callback(self.improvement)
            return

        super().mouseDoubleClickEvent(event)

    def add_choices_section(
        self,
        box_layout,
        improvement,
        remove_empowerment_callback=None,
    ):
        if improvement.catalog_id == "born_of_soil":
            self.add_born_of_soil_choices(
                box_layout,
                improvement,
                remove_empowerment_callback,
            )
            return

        if improvement.catalog_id == "spellcasting":
            self.add_spellcasting_choices(
                box_layout,
                improvement,
                remove_empowerment_callback,
            )
            return

        if improvement.catalog_id == "animal_buddy":
            self.add_animal_buddy_choices_box(
                box_layout,
                improvement,
            )
            return

        formatted_choices = self.format_choices(
            improvement.choices,
            improvement,
        ).strip()

        if not formatted_choices:
            return

        choices_label = QLabel(
            formatted_choices
        )
        choices_label.setWordWrap(True)
        choices_label.setMinimumWidth(0)
        choices_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        set_themed_stylesheet(choices_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: #222222;
                padding: 0px;
                margin: 0px;
            }
        """)
        box_layout.addWidget(choices_label)

    def add_animal_buddy_choices_box(
        self,
        box_layout,
        improvement,
    ):
        """Show Animal Buddy identity and abilities in a nested panel."""
        choices = improvement.choices or {}

        raw_name = choices.get("buddy_name")
        buddy_name = (
            self.pretty_value(raw_name)
            if raw_name and raw_name != "Missing"
            else "Unnamed Buddy"
        )

        perks = []
        base_perk = choices.get("buddy_perk")
        if base_perk and base_perk != "Missing":
            perks.append(self.pretty_value(base_perk))

        bonuses = {stat_name: 0 for stat_name in STAT_NAMES}
        for empowerment in improvement.empowerments:
            if empowerment.catalog_id == "gifted":
                extra_perk = empowerment.choices.get("buddy_perk")
                if extra_perk and extra_perk != "Missing":
                    perks.append(self.pretty_value(extra_perk))
            elif empowerment.catalog_id == "well_trained":
                stat_name = empowerment.choices.get("buddy_training_stat")
                if stat_name in bonuses:
                    bonuses[stat_name] += 1

        perks_text = ", ".join(perks) if perks else "Missing"
        dice = {stat_name: 4 for stat_name in STAT_NAMES}
        assigned = [
            (choices.get("buddy_stat_d10"), 10),
            (choices.get("buddy_stat_d8_a"), 8),
            (choices.get("buddy_stat_d8_b"), 8),
            (choices.get("buddy_stat_d6"), 6),
        ]
        for stat_name, die_size in assigned:
            if stat_name in dice and stat_name != "Missing":
                dice[stat_name] = die_size

        buddy_box = QFrame()
        buddy_box.setObjectName("AnimalBuddyInfoBox")
        set_themed_stylesheet(buddy_box, """
            QFrame#AnimalBuddyInfoBox {
                background-color: #fffdf7;
                border: 1px solid #cdaa63;
                border-radius: 9px;
            }
        """)
        buddy_layout = QVBoxLayout(buddy_box)
        buddy_layout.setContentsMargins(7, 6, 7, 7)
        buddy_layout.setSpacing(4)

        for text_value in (
            f"Name: {buddy_name}",
            f"Perk: {perks_text}",
        ):
            label = QLabel(text_value)
            label.setWordWrap(True)
            set_themed_stylesheet(label, """
                QLabel {
                    background: transparent;
                    border: none;
                    font-size: 11px;
                    font-weight: 800;
                    color: #25190f;
                    padding: 0px;
                    margin: 0px;
                }
            """)
            buddy_layout.addWidget(label)

        abilities_title = QLabel("Abilities")
        set_themed_stylesheet(abilities_title, """
            QLabel {
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: 900;
                color: #6c5428;
                padding-top: 2px;
            }
        """)
        buddy_layout.addWidget(abilities_title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)

        for index, stat_name in enumerate(STAT_NAMES):
            accent = ABILITY_ACCENTS.get(
                stat_name,
                "#6c5428",
            )

            stat_box = QFrame()
            set_themed_stylesheet(
                stat_box,
                f"""
                QFrame {{
                    background-color: #fffaf0;
                    border: 1px solid #d9bd82;
                    border-radius: 7px;
                }}
                """,
            )
            stat_layout = QVBoxLayout(stat_box)
            stat_layout.setContentsMargins(4, 3, 4, 3)
            stat_layout.setSpacing(0)

            stat_title = QLabel(self.pretty_value(stat_name))
            stat_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            set_themed_stylesheet(
                stat_title,
                f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    font-size: 9px;
                    font-weight: 800;
                    color: {accent};
                    padding: 0px;
                }}
                """,
            )

            bonus = bonuses.get(stat_name, 0)
            bonus_text = f"+{bonus}" if bonus > 0 else ""
            stat_value = QLabel(f"d{dice[stat_name]}{bonus_text}")
            stat_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            set_themed_stylesheet(
                stat_value,
                f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    font-weight: 900;
                    color: {accent};
                    padding: 0px;
                }}
                """,
            )

            stat_layout.addWidget(stat_title)
            stat_layout.addWidget(stat_value)
            grid.addWidget(stat_box, index // 3, index % 3)

        buddy_layout.addLayout(grid)
        box_layout.addWidget(buddy_box)

    def add_removable_choice_row(
        self,
        box_layout,
        text,
        improvement,
        empowerment=None,
        remove_empowerment_callback=None,
        editable=False,
        description=None,
    ):
        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 2, 0)
        row.setSpacing(0)

        bullet = ImprovementBullet()
        row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
        detail_text = str(description).strip() if description and description != "Missing" else ""
        if detail_text:
            detail_color = "#d8d0bf" if ui_theme_module.CURRENT_THEME == "dark" else "#444444"
            label_text = (f'<b>{escape_html(str(text))}</b><br>'
                          f'<span style="color:{detail_color};font-size:11px;font-weight:normal">'
                          f'{escape_html(detail_text).replace(chr(10), "<br>")}</span>')
        else:
            label_text = text
        label = QLabel(label_text)
        label.setProperty("compact_choice_line", True)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        set_themed_stylesheet(label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: #222222;
            }
        """)

        bullet.set_target(label)
        row.addWidget(label, 1, Qt.AlignmentFlag.AlignTop)

        if editable and empowerment is not None:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(18, 18)
            set_themed_stylesheet(edit_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    font-weight: 900;
                    color: black;
                }

                QPushButton:hover {
                    color: #2f5f91;
                }
            """)

            edit_btn.clicked.connect(
                lambda checked=False, i=improvement, e=empowerment:
                    self.window().edit_empowerment_choices(
                        i,
                        e,
                    )
            )

            row.addSpacing(4)
            row.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignTop)

        if (
            empowerment is not None
            and remove_empowerment_callback is not None
        ):
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            set_themed_stylesheet(remove_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
            """)

            remove_btn.clicked.connect(
                lambda checked=False, e=empowerment:
                    remove_empowerment_callback(
                        improvement,
                        e,
                    )
            )

            row.addSpacing(4)
            row.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        box_layout.addLayout(row)

    def add_born_of_soil_choices(
        self,
        box_layout,
        improvement,
        remove_empowerment_callback=None,
    ):
        title = QLabel("Lands")
        set_themed_stylesheet(
            title,
            """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
            """,
        )

        box_layout.addWidget(title)

        def add_land(
            land_name,
            description="",
            empowerment=None,
        ):
            # Keep a land name and its description as one compact text block.
            # Controls remain aligned with the land name on the right.
            row = QHBoxLayout()
            row.setContentsMargins(10, 0, 0, 0)
            row.setSpacing(4)

            description = str(description or "").strip()
            land_text = escape_html(self.pretty_value(land_name))

            if description and description != "Missing":
                description_text = escape_html(description)
                text = (
                    f'<div style="margin:0; padding:0; line-height:100%;">'
                    f'<span style="font-size:12px; font-weight:800;">'
                    f'• {land_text}</span><br>'
                    f'<span style="font-size:11px; font-weight:600;">'
                    f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{description_text}</span>'
                    f'</div>'
                )
            else:
                text = (
                    f'<span style="font-size:12px; font-weight:800;">'
                    f'• {land_text}</span>'
                )

            text_label = QLabel(text)
            text_label.setTextFormat(Qt.TextFormat.RichText)
            text_label.setWordWrap(True)
            text_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
            )
            set_themed_stylesheet(
                text_label,
                """
                QLabel {
                    border: none;
                    background: transparent;
                    padding: 0px;
                    margin: 0px;
                }
                """,
            )
            row.addWidget(text_label, 1, Qt.AlignmentFlag.AlignTop)

            if empowerment is not None:
                edit_btn = QPushButton("✎")
                edit_btn.setFixedSize(18, 18)
                set_themed_stylesheet(
                    edit_btn,
                    """
                    QPushButton {
                        background: transparent;
                        border: none;
                        font-size: 13px;
                        font-weight: 900;
                        color: black;
                        padding: 0px;
                        margin: 0px;
                    }
                    QPushButton:hover { color: #2f5f91; }
                    """,
                )
                edit_btn.clicked.connect(
                    lambda checked=False, i=improvement, e=empowerment:
                    self.window().edit_empowerment_choices(i, e)
                )
                row.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignTop)

                if remove_empowerment_callback is not None:
                    remove_btn = QPushButton("×")
                    remove_btn.setFixedSize(18, 18)
                    set_themed_stylesheet(
                        remove_btn,
                        """
                        QPushButton {
                            background: transparent;
                            border: none;
                            font-size: 14px;
                            font-weight: 900;
                            color: black;
                            padding: 0px;
                            margin: 0px;
                        }
                        QPushButton:hover { color: #aa0000; }
                        """,
                    )
                    remove_btn.clicked.connect(
                        lambda checked=False, e=empowerment:
                        remove_empowerment_callback(improvement, e)
                    )
                    row.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

            box_layout.addLayout(row)

        # Primary land
        primary_land = improvement.choices.get(
            "attuned_land"
        )

        primary_description = (
            improvement.choices.get(
                "attuned_land_description",
                "",
            )
        )

        if (
            primary_land
            and primary_land != "Missing"
        ):
            add_land(
                primary_land,
                primary_description,
            )

        # Additional lands. Keep each land name tight to its description,
        # but separate distinct lands enough to read as separate entries.
        added_land_count = 1 if (primary_land and primary_land != "Missing") else 0
        for empowerment in improvement.empowerments:
            if (
                empowerment.catalog_id
                != "additional_attuned_land"
            ):
                continue

            extra_land = (
                empowerment.choices.get(
                    "attuned_land"
                )
            )

            if (
                not extra_land
                or extra_land == "Missing"
            ):
                extra_land = "Missing"

            extra_description = (
                empowerment.choices.get(
                    "attuned_land_description",
                    "",
                )
            )

            if added_land_count:
                box_layout.addSpacing(8)
            add_land(
                extra_land,
                extra_description,
                empowerment=empowerment,
            )
            added_land_count += 1

        tell = improvement.choices.get(
            "tell"
        )

        tell_text = (
            self.pretty_value(tell)
            if tell
            and tell != "Missing"
            else "Missing Tell"
        )

        tell_label = QLabel(
            f"Tell: {tell_text}"
        )

        set_themed_stylesheet(
            tell_label,
            """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: #222222;
                padding: 2px 0px 0px 0px;
                margin: 0px;
            }
            """,
        )

        box_layout.addWidget(tell_label)

    def add_spellcasting_choices(
        self,
        box_layout,
        improvement,
        remove_empowerment_callback=None,
    ):
        magic_die = self.character.bonus_dice.dice.get("magic_die")

        # The API-authored owned description already shows Magic Die: dX and
        # its non-exploding rule. Do not display an extra duplicate label.
        title = QLabel("Schools")
        set_themed_stylesheet(title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 900;
                color: black;
                padding-top: 2px;
            }
        """)
        box_layout.addWidget(title)

        primary_school = improvement.choices.get("magic_school")
        primary_description = improvement.choices.get("magic_school_description")

        if primary_school and primary_school != "Missing":
            self.add_school_display_row(
                box_layout,
                self.pretty_value(primary_school),
                primary_description,
                improvement,
            )

        school_savant_empowerments = [
            empowerment
            for empowerment in improvement.empowerments
            if empowerment.group_id == "school_savant"
        ]

        for savant_number, empowerment in enumerate(
            school_savant_empowerments,
            start=1,
        ):
            extra_school = empowerment.choices.get(
                "magic_school"
            )
            
            extra_description = empowerment.choices.get(
                "magic_school_description"
            )

            if not extra_school or extra_school == "Missing":
                extra_school = "Missing"

            self.add_school_display_row(
                box_layout,
                self.pretty_value(extra_school),
                extra_description,
                improvement,
                empowerment=empowerment,
                remove_empowerment_callback=remove_empowerment_callback,
                display_prefix=None,
            )

    def add_school_display_row(
        self,
        box_layout,
        school_name,
        school_description,
        improvement,
        empowerment=None,
        remove_empowerment_callback=None,
        display_prefix=None,
    ):
        # Keep each school entry as a real widget with a Maximum vertical
        # size policy.  A bare child layout can absorb surplus vertical space
        # when the Improvement card is relaid out, which made repeated toggles
        # in the opposite column stretch the gaps between Spellcasting schools.
        school_row_widget = QWidget()
        school_row_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        heading_row = QHBoxLayout(school_row_widget)
        heading_row.setContentsMargins(12, 0, 0, 0)
        heading_row.setSpacing(0)
        heading_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        bullet = ImprovementBullet()
        heading_row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
        # One label for heading AND description: separate word-wrapped QLabel
        # widgets reserve independent line boxes, causing the large gap seen
        # between e.g. "Resonant Elemency" and its description. A single rich
        # text label uses a normal line break while retaining wrapping.
        school_label = QLabel()
        school_label.setObjectName("SpellcastingSchoolText")
        school_label.setTextFormat(Qt.TextFormat.RichText)
        school_label.setWordWrap(True)
        school_label.setMinimumWidth(0)
        school_label.setContentsMargins(0, 0, 0, 0)
        school_label.setMargin(0)
        school_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        school_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        safe_heading = escape_html(school_name)
        rich_text = f'<b><span style="font-size:12px;">{safe_heading}</span></b>'
        if school_description and school_description != "Missing":
            # User-entered school descriptions can contain trailing blank
            # lines. If preserved as <br> tags, those blank lines become an
            # apparent gap before the Empowerments section.
            safe_description = escape_html(
                str(school_description).strip()
            ).replace("\n", "<br>")
            rich_text += (
                '<br><span style="font-size:11px; font-weight:600;">'
                + safe_description + '</span>'
            )
        school_label.setText(rich_text)
        set_themed_stylesheet(school_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 11px;
                font-weight: 600;
                color: #222222;
                padding: 0px;
                margin: 0px;
            }
        """)
        heading_row.addWidget(school_label, 1)
        bullet.set_target(school_label)

        if empowerment is not None:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(18, 18)
            set_themed_stylesheet(edit_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                }
                QPushButton:hover { color: #2f5f91; }
            """)
            edit_btn.clicked.connect(
                lambda checked=False, i=improvement, e=empowerment:
                    self.window().edit_empowerment_choices(i, e)
            )
            heading_row.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        if empowerment is not None and remove_empowerment_callback is not None:
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            set_themed_stylesheet(remove_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                }
                QPushButton:hover { color: #aa0000; }
            """)
            remove_btn.clicked.connect(
                lambda checked=False, e=empowerment:
                    remove_empowerment_callback(improvement, e)
            )
            heading_row.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Add the constrained row as a widget, not as a free-standing layout.
        # This prevents Qt from distributing extra card height inside the row.
        box_layout.addWidget(
            school_row_widget,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

    def can_remove_empowerment(self, empowerment):
        """
        Normal empowerments can always be removed.

        For ordered/scaling empowerment groups, only the highest
        currently owned level can be removed.
        """

        option = ImprovementCatalogSystem.get_option(
            self.improvement.catalog_id
        )

        if option is None:
            return True

        scaling_groups = option.get("scaling_empowerments", {})

        # This empowerment does not belong to an ordered/scaling group.
        if empowerment.group_id not in scaling_groups:
            return True

        owned_in_group = [
            owned
            for owned in self.improvement.empowerments
            if owned.group_id == empowerment.group_id
        ]

        if not owned_in_group:
            return False

        # Scaling empowerments are added in order, so only the last
        # currently owned one may be removed.
        return empowerment is owned_in_group[-1]

    def add_sneak_attack_effects(
        self,
        box_layout,
        improvement,
        remove_empowerment_callback=None,
    ):
        """
        Display Sneak Attack's purchased effect empowerments.

        Each effect appears as its own removable row.
        """
        # All ability names originate in character_API, not hardcoded UI prose.
        option = ImprovementCatalogSystem.get_option(improvement.catalog_id, self.character)
        group = (option or {}).get("empowerment_groups", {}).get("extra_effects", {})
        effect_names = {entry["id"]: entry.get("name", entry["id"])
                        for entry in group.get("options", [])}

        effect_empowerments = [
            empowerment
            for empowerment in improvement.empowerments
            if empowerment.catalog_id in effect_names
        ]

        if not effect_empowerments:
            base_label = QLabel("Extra Effects: Base Effects Only")
            base_label.setWordWrap(True)
            set_themed_stylesheet(base_label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    font-weight: 800;
                    color: #222222;
                    padding-top: 2px;
                }
            """)
            box_layout.addWidget(base_label)
            return

        title = QLabel("Extra Effects")
        set_themed_stylesheet(title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 13px;
                font-weight: 900;
                color: black;
                padding-top: 1px;
            }
        """)
        box_layout.addWidget(title)

        for empowerment in effect_empowerments:
            row = QHBoxLayout()
            row.setContentsMargins(10, 0, 0, 0)
            row.setSpacing(4)

            bullet = ImprovementBullet()
            row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
            label = QLabel(effect_names[empowerment.catalog_id])
            label.setWordWrap(True)
            label.setProperty("compact_improvement_line", True)
            set_themed_stylesheet(label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    font-weight: 800;
                    color: #222222;
                }
            """)

            row.addWidget(label, 1)
            bullet.set_target(label)

            if remove_empowerment_callback is not None:
                remove_btn = QPushButton("×")
                remove_btn.setFixedSize(18, 18)
                set_themed_stylesheet(remove_btn, """
                    QPushButton {
                        background: transparent;
                        border: none;
                        font-size: 14px;
                        font-weight: 900;
                        color: black;
                    }

                    QPushButton:hover {
                        color: #aa0000;
                    }
                """)

                remove_btn.clicked.connect(
                    lambda checked=False, e=empowerment:
                        remove_empowerment_callback(
                            improvement,
                            e,
                        )
                )

                row.addWidget(
                    remove_btn,
                    0,
                    Qt.AlignmentFlag.AlignTop,
                )

            box_layout.addLayout(row)
        
    def add_animal_buddy_empowerments(
        self,
        box_layout,
        improvement,
        remove_empowerment_callback=None,
    ):
        gifted = [
            empowerment
            for empowerment in improvement.empowerments
            if empowerment.catalog_id == "gifted"
        ]

        well_trained = [
            empowerment
            for empowerment in improvement.empowerments
            if empowerment.catalog_id == "well_trained"
        ]

        extra_hearts = [
            empowerment
            for empowerment in improvement.empowerments
            if empowerment.group_id == "buddy_hearts"
        ]

        if not gifted and not well_trained and not extra_hearts:
            return

        title = QLabel("Empowerments")
        set_themed_stylesheet(title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 13px;
                font-weight: 900;
                color: black;
                padding-top: 4px;
            }
        """)
        box_layout.addWidget(title)

        # ------------------------------------------------------------
        # Gifted
        # ------------------------------------------------------------
        for empowerment in gifted:
            perk = empowerment.choices.get(
                "buddy_perk",
                "Missing",
            )

            self.add_animal_buddy_empowerment_row(
                box_layout,
                improvement,
                empowerment,
                f"Gifted ⇒ {self.pretty_value(perk)}",
                editable=True,
                removable=True,
                remove_empowerment_callback=remove_empowerment_callback,
            )

        # ------------------------------------------------------------
        # Well Trained
        # ------------------------------------------------------------
        for empowerment in well_trained:
            stat_name = empowerment.choices.get(
                "buddy_training_stat",
                "Missing",
            )

            same_stat_training = [
                owned
                for owned in well_trained
                if owned.choices.get("buddy_training_stat") == stat_name
            ]

            rank = (
                same_stat_training.index(empowerment) + 1
                if empowerment in same_stat_training
                else 1
            )

            is_highest_for_stat = (
                bool(same_stat_training)
                and same_stat_training[-1] is empowerment
            )

            self.add_animal_buddy_empowerment_row(
                box_layout,
                improvement,
                empowerment,
                (
                    f"Well Trained ⇒ "
                    f"{self.pretty_value(stat_name)} +{rank}"
                ),
                editable=False,
                removable=is_highest_for_stat,
                remove_empowerment_callback=remove_empowerment_callback
            )

        # ------------------------------------------------------------
        # Extra Hearts
        #
        # Only the highest currently owned scaling level can be removed.
        # ------------------------------------------------------------
        sturdy = any(str(perk).replace("_", " ").strip().lower() == "sturdy"
                     for perk in [improvement.choices.get("buddy_perk", "")] +
                     [e.choices.get("buddy_perk", "") for e in gifted])
        for index, empowerment in enumerate(extra_hearts):
            heart_number = index + (3 if sturdy else 2)

            is_highest = (
                empowerment is extra_hearts[-1]
            )

            self.add_animal_buddy_empowerment_row(
                box_layout,
                improvement,
                empowerment,
                f"Extra Heart ⇒ {heart_number} Hearts",
                editable=False,
                removable=is_highest,
                remove_empowerment_callback=remove_empowerment_callback,
            )
            
    def add_animal_buddy_empowerment_row(
        self,
        box_layout,
        improvement,
        empowerment,
        text,
        editable=False,
        removable=True,
        remove_empowerment_callback=None,
    ):
        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 0, 0)
        row.setSpacing(4)

        bullet = ImprovementBullet()
        row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
        label = QLabel(text)
        label.setWordWrap(True)
        set_themed_stylesheet(label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: #222222;
            }
        """)

        row.addWidget(label, 1)
        bullet.set_target(label)

        if editable:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(18, 18)
            set_themed_stylesheet(edit_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    font-weight: 900;
                    color: black;
                }

                QPushButton:hover {
                    color: #2f5f91;
                }
            """)

            edit_btn.clicked.connect(
                lambda checked=False, i=improvement, e=empowerment:
                    self.window().edit_empowerment_choices(
                        i,
                        e,
                    )
            )

            row.addWidget(edit_btn)

        if (
            removable
            and remove_empowerment_callback is not None
        ):
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            set_themed_stylesheet(remove_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
            """)

            remove_btn.clicked.connect(
                lambda checked=False, e=empowerment:
                    remove_empowerment_callback(
                        improvement,
                        e,
                    )
            )

            row.addWidget(remove_btn)

        box_layout.addLayout(row)
        
    def add_merged_empowerment_remove_row(
        self,
        box_layout,
        improvement,
        empowerment_catalog_id,
        display_name,
        remove_empowerment_callback=None,
    ):
        empowerment = next(
            (
                owned
                for owned in improvement.empowerments
                if owned.catalog_id == empowerment_catalog_id
            ),
            None,
        )

        if empowerment is None:
            return

        # These merged rows still use character_API.py as the authoritative
        # source for their text.  Previously this special row rendered only
        # the empowerment name, so owned descriptions such as Thing Talker
        # silently disappeared after purchase.
        empowerment_option = None
        parent_option = IMPROVEMENT_CATALOG.get(improvement.catalog_id, {})
        for option in parent_option.get("empowerments", []):
            if option.get("id") == empowerment_catalog_id:
                empowerment_option = option
                break

        description = ""
        if empowerment_option is not None:
            description = (
                empowerment_option.get("owned_description")
                or empowerment_option.get("description")
                or ""
            )

        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 0, 0)
        row.setSpacing(4)

        bullet = ImprovementBullet()
        row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(1)

        label = QLabel(display_name)
        label.setWordWrap(True)
        set_themed_stylesheet(label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: #222222;
            }
        """)
        text_column.addWidget(label)
        bullet.set_target(label)

        if description:
            description_label = QLabel(description)
            description_label.setTextFormat(Qt.TextFormat.RichText)
            description_label.setWordWrap(True)
            description_label.setMinimumWidth(0)
            description_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            description_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            set_themed_stylesheet(description_label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    color: #222222;
                    padding: 0px;
                    margin: 0px;
                }
            """)
            text_column.addWidget(description_label)

        row.addLayout(text_column, 1)

        if remove_empowerment_callback is not None:
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            set_themed_stylesheet(remove_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
            """)

            remove_btn.clicked.connect(
                lambda checked=False, e=empowerment:
                    remove_empowerment_callback(
                        improvement,
                        e,
                    )
            )

            row.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        box_layout.addLayout(row)

class EmpowermentRow(QWidget):
    """
    Represents a single empowerment under an improvement.
    Shows its name, description, cost, and remove/edit buttons.
    """
    def __init__(
        self,
        parent_improvement,
        empowerment,
        remove_callback=None,
        edit_callback=None,
        ):
        super().__init__()
        self.empowerment = empowerment
        self.parent_improvement = parent_improvement
        self.edit_callback = edit_callback
        self.remove_callback = remove_callback

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 0, 0, 0)
        outer.setSpacing(10)

        self.main_box = QFrame()
        set_themed_stylesheet(self.main_box, """
            QFrame {
                background-color: #a9d5ea;
                border: none;
                border-radius: 14px;
            }
        """)
        self.main_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        box_layout = QVBoxLayout(self.main_box)
        box_layout.setContentsMargins(12, 4, 12, 4)
        box_layout.setSpacing(1)

        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedSize(18, 18)
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
        self.remove_btn.clicked.connect(self.on_remove_clicked)
        self.name_label = QLabel(f"↳ {empowerment.name}")
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred
        )
        set_themed_stylesheet(self.name_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 800;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_label, 1)
        name_row.addWidget(self.remove_btn)
        box_layout.addLayout(name_row)

        description = empowerment.description.strip()

        if description:
            description_label = QLabel(description)
            description_label.setTextFormat(Qt.TextFormat.RichText)
            description_label.setWordWrap(True)
            description_label.setMinimumWidth(0)
            description_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred
            )
            set_themed_stylesheet(description_label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }
            """)
            box_layout.addWidget(description_label)

        self.count_box = QLabel(str(empowerment.cost))
        self.count_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_box.setFixedSize(38, 38)
        set_themed_stylesheet(self.count_box, """
            QLabel {
                background-color: #a9d5ea;
                border: none;
                border-radius: 19px;
                font-size: 15px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }
        """)

        outer.addWidget(self.main_box, 1)
        outer.addWidget(self.count_box, 0, Qt.AlignmentFlag.AlignTop)

    def mouseDoubleClickEvent(self, event):
        if self.edit_callback is None:
            return

        pos = event.position().toPoint()

        local_name_pos = self.name_label.mapFrom(self, pos)

        if self.name_label.rect().contains(local_name_pos):
            self.edit_callback(self.parent_improvement, self.empowerment)
            return

        super().mouseDoubleClickEvent(event)

    def on_remove_clicked(self):
        if self.remove_callback is not None:
            self.remove_callback(self.parent_improvement, self.empowerment)


class SkilledAtGroupRow(QWidget):
    """
    Groups multiple Skilled At improvements into one combined UI block.
    The whole group can be expanded/collapsed.
    """

    def __init__(
        self,
        skilled_improvements,
        remove_callback,
        edit_callback,
    ):
        super().__init__()

        self.skilled_improvements = skilled_improvements
        self.remove_callback = remove_callback
        self.edit_callback = edit_callback

        # Use the first Skilled At entry to remember the group's state.
        self.expanded = any(
            getattr(improvement, "expanded", False)
            for improvement in skilled_improvements
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        self.main_box = QFrame()

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.main_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )        
        set_themed_stylesheet(self.main_box, f"""
            QFrame {{
                background-color: {BLUE};
                border: none;
                border-radius: 14px;
            }}
        """)

        box_layout = QVBoxLayout(self.main_box)
        box_layout.setContentsMargins(12, 4, 12, 4)
        box_layout.setSpacing(1)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.expand_btn = QPushButton(
            "▾" if self.expanded else "▸"
        )

        self.expand_btn.setFixedSize(22, 22)

        set_themed_stylesheet(self.expand_btn, """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 17px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #2f5f91;
            }
        """)

        self.expand_btn.clicked.connect(
            self.toggle_expanded
        )

        title = QLabel("Skilled At")

        set_themed_stylesheet(title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 16px;
                font-weight: 900;
                color: black;
            }
        """)

        header_row.addWidget(self.expand_btn)
        header_row.addWidget(title, 1)

        self.remove_all_btn = QPushButton("×")

        self.remove_all_btn.setFixedSize(20, 20)

        set_themed_stylesheet(
            self.remove_all_btn,
                """
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
                """
            )

        self.remove_all_btn.clicked.connect(
            self.remove_all_skilled_at
        )

        header_row.addWidget(
            self.remove_all_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        box_layout.addLayout(header_row)

        # ----------------------------------------------------
        # Expandable content
        # ----------------------------------------------------

        self.content_widget = QWidget()

        content_layout = QVBoxLayout(
            self.content_widget
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(5)

        rules_label = QLabel(
            "Choose a non-combat skill with the GM. "
            "You succeed on moderately difficult checks, 9 or less, "
            "and may add up to +3 on harder checks. "
            "Does not stack with other improvement bonuses."
        )

        rules_label.setWordWrap(True)

        set_themed_stylesheet(rules_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 11px;
                color: #222222;
            }
        """)

        content_layout.addWidget(
            rules_label
        )

        for improvement in skilled_improvements:
            skill = improvement.choices.get(
                "skill_name",
                "Missing",
            )

            description = improvement.choices.get(
                "skill_description",
                "",
            ).strip()

            row = QHBoxLayout()

            bullet = ImprovementBullet()
            row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
            label = QLabel(str(skill).replace('_', ' ').title())
            bullet.set_target(label)

            set_themed_stylesheet(label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    font-weight: 800;
                    color: #222222;
                }
            """)

            label.mouseDoubleClickEvent = (
                lambda event, imp=improvement:
                    self.edit_callback(imp)
            )

            remove_btn = QPushButton("×")

            set_themed_stylesheet(remove_btn, """
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

            remove_btn.setFixedSize(
                18,
                18,
            )

            remove_btn.clicked.connect(
                lambda checked=False, imp=improvement:
                    self.remove_callback(imp)
            )

            row.addWidget(
                label,
                1,
            )

            row.addWidget(
                remove_btn
            )

            content_layout.addLayout(
                row
            )

            if description:
                description_label = QLabel(
                    description
                )

                description_label.setWordWrap(
                    True
                )

                set_themed_stylesheet(
                    description_label,
                    """
                    QLabel {
                        border: none;
                        background: transparent;
                        font-size: 11px;
                        color: #222222;
                        padding-left: 18px;
                    }
                    """
                )

                content_layout.addWidget(
                    description_label
                )

        box_layout.addWidget(
            self.content_widget
        )

        self.content_widget.setVisible(
            self.expanded
        )

        # ----------------------------------------------------
        # Cost bubble
        # ----------------------------------------------------

        total_cost = sum(
            improvement.total_cost()
            for improvement in skilled_improvements
        )

        self.count_box = QLabel(
            str(total_cost)
        )

        self.count_box.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.count_box.setFixedSize(
            34,
            34,
        )

        set_themed_stylesheet(
            self.count_box,
            f"""
                QLabel {{
                    background-color: {BLUE};
                    border: none;
                    border-radius: 17px;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }}
                """
            )

        outer.addWidget(
            self.main_box,
            1,
        )

        outer.addWidget(
            self.count_box,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def remove_all_skilled_at(self):
        window = self.window()

        if hasattr(
            window,
            "confirm_remove_skilled_at_group",
        ):
            window.confirm_remove_skilled_at_group(
                self.skilled_improvements
            )

    def toggle_expanded(self):
        self.expanded = not self.expanded

        # Keep every Skilled At purchase in the group synchronized.
        for improvement in self.skilled_improvements:
            improvement.expanded = self.expanded

        # Recalculate just this group rather than rebuilding all cards,
        # which used to reset scroll position and remeasure the other column.
        self.content_widget.setVisible(self.expanded)
        self.expand_btn.setText("▾" if self.expanded else "▸")
        self.content_widget.updateGeometry()
        self.main_box.layout().invalidate()
        self.updateGeometry()
        window = self.window()
        layout = getattr(window, "improvement_list_layout", None)
        if hasattr(layout, "_items") and hasattr(window, "refresh_improvement_scroll_geometry"):
            try:
                window.refresh_improvement_scroll_geometry(changed_widget=self)
                return
            except TypeError:
                pass  # Older UIs use the previous refresh signature.
        if hasattr(window, "refresh_improvements"):
            window.refresh_improvements()


class PaidHeightenedAbilityGroup(QWidget):
    """
    Groups multiple Heightened Ability improvements into one combined UI block.
    The whole group can be expanded/collapsed.
    """

    def __init__(self, owner, purchases):
        super().__init__()
        self.owner = owner
        self.purchases = purchases
        self.improvement = purchases[0]
        self.display = {"name": "Heightened Ability"}
        self.remove_callback = owner.confirm_remove_improvement
        self.edit_callback = owner.edit_improvement_choices

        # Use the first Heightened Ability entry to remember the group's state.
        self.expanded = any(
            getattr(improvement, "expanded", False)
            for improvement in purchases
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        self.main_box = QFrame()

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.main_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )        
        set_themed_stylesheet(self.main_box, f"""
            QFrame {{
                background-color: {BLUE};
                border: none;
                border-radius: 14px;
            }}
        """)

        box_layout = QVBoxLayout(self.main_box)
        box_layout.setContentsMargins(12, 4, 12, 4)
        box_layout.setSpacing(1)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.expand_btn = QPushButton(
            "▾" if self.expanded else "▸"
        )

        self.expand_btn.setFixedSize(22, 22)

        set_themed_stylesheet(self.expand_btn, """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 17px;
                font-weight: 900;
                color: black;
                padding: 0px;
                margin: 0px;
            }

            QPushButton:hover {
                color: #2f5f91;
            }
        """)

        self.expand_btn.clicked.connect(
            self.toggle_expanded
        )

        title = QLabel("Heightened Ability")
        self.name_label = title
        self.arrow_btn = self.expand_btn

        set_themed_stylesheet(title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 16px;
                font-weight: 900;
                color: black;
            }
        """)

        header_row.addWidget(self.expand_btn)
        header_row.addWidget(title, 1)

        self.remove_all_btn = QPushButton("×", self.main_box)

        self.remove_all_btn.setFixedSize(20, 20)

        set_themed_stylesheet(
            self.remove_all_btn,
                """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
                """
            )

        self.remove_all_btn.clicked.connect(
            self.remove_all_heightened
        )

        self.remove_all_btn.raise_()
        header_row.addSpacing(20)

        box_layout.addLayout(header_row)

        # ----------------------------------------------------
        # Expandable content
        # ----------------------------------------------------

        self.content_widget = QWidget()

        content_layout = QVBoxLayout(
            self.content_widget
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(0)

        display_purchases = list(purchases)
        free_tiers = {}
        for stat_name in owner.character.free_heightened_ability_stats:
            free_tiers[stat_name] = free_tiers.get(stat_name, 0) + 1
            if any(item.choices.get("stat_name") == stat_name for item in purchases):
                display_purchases.append(Improvement(
                    id=f"free_heightened_{stat_name}", catalog_id="heightened_ability",
                    name="Heightened Ability", cost=free_tiers[stat_name], description="",
                    source="free", choices={"stat_name": stat_name},
                ))
        display_purchases.sort(key=lambda item: (
            STAT_NAMES.index(item.choices["stat_name"]), item.cost
        ))

        for improvement in display_purchases:
            stat_name = improvement.choices.get("stat_name", "Missing")
            # Backend normalizes each purchase cost to its resulting bonus tier.
            new_bonus = int(improvement.cost)
            skill = f"{stat_name.title()} +{new_bonus - 1} → +{new_bonus}"
            description = ""

            row = QHBoxLayout()
            # Match the horizontal inset used by other improvement sub-items
            # (for example Animal Buddy empowerments), so bullets and labels
            # share the same visual column.
            row.setContentsMargins(10, 0, 0, 0)
            row.setSpacing(4)

            bullet = ImprovementBullet()
            row.addWidget(bullet, 0, Qt.AlignmentFlag.AlignTop)
            label = QLabel(f"{skill} · " + (("Free" if improvement.cost == 1 else f"{improvement.cost - 1} IP · free slot") if improvement.source == "free" else f"{improvement.cost} IP"))
            label.setProperty("compact_improvement_line", True)
            bullet.set_target(label)

            set_themed_stylesheet(label, """
                QLabel {
                    border: none;
                    background: transparent;
                    font-size: 12px;
                    font-weight: 800;
                    color: #222222;
                }
            """)

            remove_btn = LineRemoveButton(label)

            set_themed_stylesheet(remove_btn, """
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }

                QPushButton:hover {
                    color: #aa0000;
                }
            """)


            remove_btn.setVisible(
                improvement.source != "free"
                and ImprovementSystem.can_remove_heightened(owner.character, improvement)
            )
            remove_btn.clicked.connect(
                lambda checked=False, imp=improvement:
                    self.remove_callback(imp)
            )

            row.addWidget(
                label,
                1,
            )

            row.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

            content_layout.addLayout(
                row
            )

            if description:
                description_label = QLabel(
                    description
                )

                description_label.setWordWrap(
                    True
                )

                set_themed_stylesheet(
                    description_label,
                    """
                    QLabel {
                        border: none;
                        background: transparent;
                        font-size: 11px;
                        color: #222222;
                        padding-left: 18px;
                    }
                    """
                )

                content_layout.addWidget(
                    description_label
                )

        box_layout.addWidget(
            self.content_widget
        )

        self.content_widget.setVisible(
            self.expanded
        )

        # ----------------------------------------------------
        # Cost bubble
        # ----------------------------------------------------

        total_cost = sum(
            improvement.total_cost()
            for improvement in purchases
        )

        total_cost += sum(item.cost - 1 for item in display_purchases if item.source == "free")
        self.count_box = QLabel(
            str(total_cost)
        )

        self.count_box.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.count_box.setFixedSize(
            34,
            34,
        )

        set_themed_stylesheet(
            self.count_box,
            f"""
                QLabel {{
                    background-color: {BLUE};
                    border: none;
                    border-radius: 17px;
                    font-size: 14px;
                    font-weight: 900;
                    color: black;
                    padding: 0px;
                    margin: 0px;
                }}
                """
            )

        outer.addWidget(
            self.main_box,
            1,
        )

        outer.addWidget(
            self.count_box,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.remove_all_btn.move(
            self.main_box.width() - self.remove_all_btn.width() - 6, 6
        )

    def remove_all_heightened(self):
        window = self.owner

        if hasattr(
            window,
            "confirm_remove_heightened_group",
        ):
            window.confirm_remove_heightened_group(
                self.purchases
            )

    def toggle_expanded(self):
        self.expanded = not self.expanded

        # Keep every Heightened Ability purchase in the group synchronized.
        for improvement in self.purchases:
            improvement.expanded = self.expanded

        # Recalculate just this group rather than rebuilding all cards,
        # which used to reset scroll position and remeasure the other column.
        self.content_widget.setVisible(self.expanded)
        self.expand_btn.setText("▾" if self.expanded else "▸")
        self.content_widget.updateGeometry()
        self.main_box.layout().invalidate()
        self.updateGeometry()
        window = self.owner
        layout = getattr(window, "improvement_list_layout", None)
        if hasattr(layout, "_items") and hasattr(window, "refresh_improvement_scroll_geometry"):
            try:
                window.refresh_improvement_scroll_geometry(changed_widget=self)
                return
            except TypeError:
                pass  # Older UIs use the previous refresh signature.
        if hasattr(window, "refresh_improvements"):
            window.refresh_improvements()


class HeightenedAbilityRow(ImprovementRow):
    def __init__(
        self,
        character,
        stat_name,
        remove_callback,
        count=1,
        paid_cost=0,
    ):
        self.stat_name = stat_name
        self.free_remove_callback = remove_callback
        self.heightened_count = max(1, int(count))
        self.heightened_paid_cost = max(0, int(paid_cost))

        window = None

        # Store expanded state on the character choices-like runtime data
        # instead of on the temporary Improvement object.
        expanded_states = getattr(
            character,
            "_free_heightened_expanded",
            {},
        )

        expanded = expanded_states.get(
            stat_name,
            False,
        )

        display_improvement = Improvement(
            id=f"free_heightened_paid_{stat_name}",
            catalog_id="heightened_ability",
            name="Heightened Ability",
            cost=1,
            description="",
            source="ip",
            choices={
                "stat_name": stat_name,
            },
            empowerments=[],
            expanded=expanded,
        )

        super().__init__(
            character,
            display_improvement,
            self.remove_heightened,
            edit_callback=None,
            remove_empowerment_callback=None,
        )

        suffix = (
            f" +{self.heightened_count}"
            if self.heightened_count > 1
            else ""
        )
        self.name_label.setText(
            f"Heightened Ability: {stat_name.title()}{suffix}"
        )
        self.count_box.setText(
            str(self.heightened_paid_cost)
            if self.heightened_paid_cost > 0
            else "F"
        )

        # Free Heightened Ability changes are managed from the dedicated
        # FREE control. Keep the row informational instead of giving it the
        # same destructive X used for purchased Improvements.
        self.remove_btn.hide()

    def remove_heightened(self, improvement):
        self.free_remove_callback(
            self.stat_name
        )

    def on_arrow_clicked(self):
        new_expanded = not self.improvement.expanded

        self.improvement.expanded = new_expanded

        if not hasattr(
            self.character,
            "_free_heightened_expanded",
        ):
            self.character._free_heightened_expanded = {}

        self.character._free_heightened_expanded[
            self.stat_name
        ] = new_expanded

        window = self.window()

        if hasattr(window, "refresh_improvements"):
            window.refresh_improvements()
            
class ImprovementsMixin:
    def build_improvements_column(self, main_layout):
        imp_frame = QFrame()
        self.improvements_frame = imp_frame
        imp_frame.setObjectName("ImprovementsFrame")
        imp_frame.setFixedHeight(REGULAR_SHEET_HEIGHT)

        imp_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        # Target only the outer frame. Otherwise the QScrollArea, which is
        # also a QFrame, may inherit the same border.
        set_themed_stylesheet(imp_frame, """
            QFrame#ImprovementsFrame {
                background-color: white;
                border: 3px solid black;
                border-radius: 14px;
            }
        """)

        imp_layout = QVBoxLayout(imp_frame)
        imp_layout.setContentsMargins(10, 10, 10, 10)
        imp_layout.setSpacing(4)

        # ============================================================
        # Header
        # ============================================================

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        imp_title = QLabel("Improvements")
        imp_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        set_themed_stylesheet(imp_title, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 22px;
                font-weight: 800;
                color: black;
            }
        """)

        self.count_box = IPLabel("0 / 0")
        self.count_box.setFixedSize(70, 32)
        self.count_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(self.count_box, f"""
            QLabel {{
                background-color: {BLUE};
                border: 2px solid {BLUE};
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                color: black;
                padding: 0px;
                margin: 0px;
            }}
        """)

        header.addStretch()
        header.addWidget(imp_title)
        header.addStretch()
        header.addWidget(self.count_box)

        imp_layout.addLayout(header)

        # ============================================================
        # Scrollable improvement rows
        # ============================================================

        self.improvement_scroll = QScrollArea()
        self.improvement_scroll.setWidgetResizable(False)
        self.improvement_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.improvement_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Keep wheel/trackpad scrolling, but do not display the intrusive
        # scrollbar or let its changing width move the item cards.
        self.improvement_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        set_themed_stylesheet(self.improvement_scroll, """
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

            QScrollBar::handle:vertical:hover {
                background-color: #79b8d4;
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

        self.improvement_list_widget = QWidget()
        set_themed_stylesheet(self.improvement_list_widget, 
            "background: transparent;"
        )
        self.improvement_list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.improvement_list_layout = QVBoxLayout(
            self.improvement_list_widget
        )
        self.improvement_list_layout.setContentsMargins(0, 0, 2, 0)

        self.improvement_list_layout.setSpacing(8)
        self.improvement_list_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.improvement_list_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize
        )
        
        self.improvement_scroll.setWidget(
            self.improvement_list_widget
        )

        self.improvement_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.improvement_scroll.setMinimumHeight(0)
        self.improvement_scroll.setFixedHeight(0)

        imp_layout.addWidget(self.improvement_scroll)

        # ============================================================
        # Add button and free heightened ability
        # ============================================================

        self.add_improvement_btn = BigPlusButton("+")
        self.add_improvement_btn.clicked.connect(self.add_improvement_from_ui)
        imp_layout.addWidget(self.add_improvement_btn)

        self.free_heightened_label = QLabel()
        self.free_heightened_label.setWordWrap(False)
        self.free_heightened_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.free_heightened_label.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.free_heightened_label.mousePressEvent = (
            lambda event: self.manage_free_heightened_abilities_from_ui()
        )
        set_themed_stylesheet(self.free_heightened_label, """
            QLabel {
                border: none;
                background: transparent;
                font-size: 17px;
                font-weight: 900;
                color: #aa0000;
                padding: 0px;
                margin: 0px;
            }
        """)

        imp_layout.addWidget(
            self.free_heightened_label,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        imp_layout.addStretch()
        
        main_layout.addWidget(
            imp_frame,
            3,
            Qt.AlignmentFlag.AlignTop
        )


    def confirm_purchase_cost_matches_list(
        self,
        purchase,
        choices,
        listed_cost,
    ):
        """Warn before spending IP when the picker cost is not the real cost."""
        try:
            preview_character = deepcopy(self.character)
            before_used_ip = int(preview_character.progression.used_IP)
            preview_purchase = deepcopy(purchase)
            preview_choices = deepcopy(choices or {})

            if not ImprovementSystem.buy_purchase(
                preview_character,
                preview_purchase,
                choices=preview_choices,
            ):
                # Let the normal purchase path report a failure.  This helper
                # exists only to warn about a cost mismatch.
                return True

            actual_cost = (
                int(preview_character.progression.used_IP)
                - before_used_ip
            )
        except Exception:
            # Never block a valid purchase just because the defensive preview
            # could not be produced.  The backend still performs its normal
            # affordability validation when the real purchase is attempted.
            return True

        listed_cost = int(listed_cost)

        if actual_cost == listed_cost:
            return True

        name = str(
            purchase.get("name")
            or purchase.get("catalog_id")
            or "This improvement"
        )

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("IP Cost Warning")
        message.setText(
            f"{name} was listed as {listed_cost} IP, but this purchase "
            f"will spend {actual_cost} IP."
        )
        message.setInformativeText(
            f"Do you want to continue and spend {actual_cost} IP?"
        )
        message.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )
        message.setDefaultButton(QMessageBox.StandardButton.No)

        return (
            message.exec()
            == QMessageBox.StandardButton.Yes
        )

    def add_improvement_from_ui(self):
        if self.block_if_readonly():
            return

        browse_only = self.character.progression.available_IP <= 0

        if browse_only:
            # Temporarily give the purchase-list builder enough IP to return
            # everything that is structurally available.
            # This does not buy anything or permanently change the character.
            original_current_ip = self.character.progression.current_IP

            try:
                self.character.progression.current_IP = (
                    self.character.progression.used_IP + 999999
                )

                options = ImprovementSystem.get_available_purchases(
                    self.character
                )

            finally:
                self.character.progression.current_IP = original_current_ip

        else:        
            options = ImprovementSystem.get_available_purchases(
                self.character
            )

        options = [
            option
            for option in options
            if isinstance(option, dict)
            if option.get("source") != "species"
            and "species" not in option.get("tags", [])
        ]

        if getattr(
            self.character,
            "creation_rules_active",
            False,
        ):
            mode = getattr(
                self.character,
                "creation_improvement_mode",
                "all",
            )

            selected_ids = set(
                getattr(
                    self.character,
                    "creation_improvement_ids",
                    [],
                )
            )

            allow_custom = getattr(
                self.character,
                "creation_allow_custom_improvements",
                True,
            )

            filtered_options = []

            for option in options:
                kind = option.get("kind")
                catalog_id = option.get(
                    "catalog_id"
                )

                # Custom Improvement has its own rule.
                if catalog_id == "custom":
                    if allow_custom:
                        filtered_options.append(
                            option
                        )
                    continue

                rule_catalog_id = (
                    option.get(
                        "parent_catalog_id"
                    )
                    if kind == "empowerment"
                    else catalog_id
                )

                if (
                    mode == "allow_only"
                    and rule_catalog_id
                    not in selected_ids
                ):
                    continue

                if (
                    mode == "ban"
                    and rule_catalog_id
                    in selected_ids
                ):
                    continue

                filtered_options.append(
                    option
                )

            options = filtered_options

        if not options:
            QMessageBox.information(
                self,
                "No Available Improvements",
                "There are no improvements or empowerments you can currently buy."
            )
            return

        dialog = ImprovementPickerDialog(
            options,
            self,
            browse_only=browse_only
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_option = dialog.selected_option

        if selected_option is None:
            QMessageBox.warning(
                self,
                "No Selection",
                "No improvement was selected."
            )
            return

        # Keep the cost exactly as it was shown in the Improvement list.
        # Some purchases (for example Heightened Ability and Animal Buddy's
        # Well Trained) can become more or less expensive after choices are
        # made.  We compare the displayed cost with the amount the backend
        # will actually spend before committing the purchase.
        listed_cost = int(selected_option.get("cost", 0))

        required_choices = selected_option.get("requires_choices", [])

        if selected_option.get("catalog_id") == "upgrade_to_spellcasting":
            required_choices = [
                "magic_school",
                "magic_school_description",
            ]
            
        choices = {}
        allowed_buddy_training_stats = None
        if (
            selected_option.get("kind") == "empowerment"
            and selected_option.get("parent_catalog_id") == "animal_buddy"
            and selected_option.get("catalog_id") == "well_trained"
        ):
            parent_improvement_id = selected_option.get(
                "improvement_id"
            )

            animal_buddy = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id == parent_improvement_id
                        and improvement.catalog_id == "animal_buddy"
                    )
                ),
                None,
            )

            if animal_buddy is None:
                QMessageBox.warning(
                    self,
                    "Animal Buddy Error",
                    "Could not find the Animal Buddy improvement.",
                )
                return

            available_ip = (
                self.character.progression.available_IP
            )

            allowed_buddy_training_stats = []

            for stat_name in STAT_NAMES:
                current_bonus = sum(
                    1
                    for empowerment in animal_buddy.empowerments
                    if (
                        empowerment.catalog_id == "well_trained"
                        and empowerment.choices.get(
                            "buddy_training_stat"
                        ) == stat_name
                    )
                )

                next_cost = current_bonus + 1

                if next_cost <= available_ip:
                    allowed_buddy_training_stats.append(
                        stat_name
                    )

            if not allowed_buddy_training_stats:
                QMessageBox.information(
                    self,
                    "Not Enough IP",
                    (
                        "You do not have enough IP to increase "
                        "any of your buddy's abilities."
                    ),
                )
                return
                
        if required_choices:
            choice_dialog = ChoiceInputDialog(
                required_choices,
                title=f"{selected_option['name']} Choices",
                parent=self,
                allowed_buddy_training_stats=(
                    allowed_buddy_training_stats
                ),            
            )

            if selected_option.get("catalog_id") == "heightened_ability":
                field = choice_dialog.inputs["stat_name"]
                for index in range(field.count() - 1, -1, -1):
                    stat_name = field.itemData(index)
                    cost = StatSystem.heightened_ability_cost(self.character, stat_name)
                    if cost > self.character.progression.available_IP:
                        field.removeItem(index)
                if field.count() == 0:
                    return
                field.setCurrentIndex(0)

            dialog_result = choice_dialog.exec()

            if dialog_result == QDialog.DialogCode.Accepted:
                choices = choice_dialog.choices

            else:
                if selected_option.get("catalog_id") == "animal_buddy":
                    return
                
                choices = {
                    choice_key: "Missing"
                    for choice_key in required_choices
                }

        if selected_option.get("catalog_id") == "heightened_ability":
            stat_name = choices.get("stat_name")
            if stat_name not in STAT_NAMES:
                return
            actual_cost = StatSystem.heightened_ability_cost(self.character, stat_name)
            if actual_cost > self.character.progression.available_IP:
                QMessageBox.warning(self, "Not Enough IP",
                                    f"This increase costs {actual_cost} IP.")
                return
            if not ask_yes_no(self, "Heightened Ability",
                             f"Increase {stat_name.title()} to "
                             f"+{self.character.stats.get_stat(stat_name).bonus + 1} "
                             f"for {actual_cost} IP?"):
                return
            selected_option = dict(selected_option, cost=actual_cost)

        existing_improvement_ids = {
            improvement.id
            for improvement
            in self.character.improvements.list_of_taken_improvements
        }

        if (
            selected_option.get("kind") == "empowerment"
            and selected_option.get("parent_catalog_id") == "animal_buddy"
            and selected_option.get("catalog_id") == "well_trained"
        ):
            selected_stat = choices.get("buddy_training_stat")

            if (
                not selected_stat
                or selected_stat == "Missing"
            ):
                QMessageBox.warning(
                    self,
                    "Missing Ability",
                    "Choose which Animal Buddy ability to improve.",
                )
                return


            parent_improvement_id = selected_option.get(
                "improvement_id"
            )

            animal_buddy = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id == parent_improvement_id
                        and improvement.catalog_id == "animal_buddy"
                    )
                ),
                None,
            )

            if animal_buddy is None:
                QMessageBox.warning(
                    self,
                    "Animal Buddy Error",
                    "Could not find the Animal Buddy improvement.",
                )
                return

            current_bonus = sum(
                1
                for empowerment in animal_buddy.empowerments
                if (
                    empowerment.catalog_id == "well_trained"
                    and empowerment.choices.get(
                        "buddy_training_stat"
                    ) == selected_stat
                )
            )

            actual_cost = current_bonus + 1

            if actual_cost > self.character.progression.available_IP:
                QMessageBox.warning(
                    self,
                    "Not Enough IP",
                    (
                        f"Increasing {selected_stat.title()} "
                        f"to +{current_bonus + 1} costs "
                        f"{actual_cost} IP."
                    ),
                )
                return

            # IMPORTANT:
            # Change the purchase cost BEFORE buy_purchase().
            selected_option["cost"] = actual_cost


        if not self.confirm_purchase_cost_matches_list(
            selected_option,
            choices,
            listed_cost,
        ):
            return

        success = ImprovementSystem.buy_purchase(
            self.character,
            selected_option,
            choices=choices,
        )

        if not success:
            QMessageBox.warning(
                self,
                "Purchase Failed",
                "Could not buy this improvement or empowerment."
            )
            return

        if selected_option.get("kind") == "custom":
            added = next((item for item in
                          self.character.improvements.list_of_taken_improvements
                          if item.id not in existing_improvement_ids
                          and item.catalog_id == "custom"), None)
            if added is not None:
                added.choices["_custom_icon"] = selected_option.get("icon", "")

        if (
            selected_option.get("catalog_id") in {"spellcasting", "magic_novice"}
            and selected_option.get("kind", "base") != "empowerment"
        ):
            purchased_spellcasting = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id not in existing_improvement_ids
                        and improvement.catalog_id in {"spellcasting", "magic_novice"}
                    )
                ),
                None,
            )

            if purchased_spellcasting is not None:
                self.offer_spellcasting_verbs_note(
                    purchased_spellcasting
                )



        if (
            selected_option.get("kind") == "empowerment"
            and selected_option.get("parent_catalog_id") == "spellcasting"
        ):
            parent_improvement_id = selected_option.get("improvement_id")

            spellcasting_improvement = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id == parent_improvement_id
                        and improvement.catalog_id == "spellcasting"
                    )
                ),
                None,
            )

            if (
                spellcasting_improvement is not None
                and not spellcasting_improvement.choices.get("_verbs_note_created")
            ):
                self.offer_spellcasting_verbs_note(
                    spellcasting_improvement
                )
        
        if (
            selected_option.get("catalog_id") == "sneak_attack"
            and selected_option.get("kind", "base") != "empowerment"
        ):
            purchased_sneak_attack = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id not in existing_improvement_ids
                        and improvement.catalog_id == "sneak_attack"
                    )
                ),
                None,
            )

            if purchased_sneak_attack is not None:
                self.offer_sneak_attack_note(
                    purchased_sneak_attack
                )


        if (
            selected_option.get("kind") == "empowerment"
            and selected_option.get("catalog_id") != "extra_effects"
        ):
            parent_improvement_id = (
                selected_option.get("improvement_id")
            )

            sneak_attack_improvement = next(
                (
                    improvement
                    for improvement
                    in self.character.improvements.list_of_taken_improvements
                    if (
                        improvement.id == parent_improvement_id
                        and improvement.catalog_id == "sneak_attack"
                    )
                ),
                None,
            )

            if sneak_attack_improvement is not None:
                if sneak_attack_improvement.choices.get(
                    "_sneak_attack_note_created"
                ):
                    # Note already chosen earlier:
                    # update it automatically, no popup.
                    existing_note = self.find_note_by_title(
                        "Sneak Attack"
                    )

                    if existing_note is not None:
                        existing_note.text = self.build_sneak_attack_note_text(
                            sneak_attack_improvement
                        )
                        existing_note.expanded = True

                        self.refresh_all()

                else:
                    # User has never chosen to move Sneak Attack to a note,
                    # so ask again after this new effect.
                    self.offer_sneak_attack_note(
                        sneak_attack_improvement
                    )
        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()


    def replace_expanded_improvement_row(self, old_row):
        """Replace just the clicked card; keep other cards and scroll intact.

        The desktop redesign uses IndependentTwoColumnImprovementLayout,
        whose _items list is ordered and which has no insertWidget API.
        Fallback to a full refresh if another layout implementation is used.
        """
        layout = self.improvement_list_layout
        index = next(
            (i for i in range(layout.count())
             if layout.itemAt(i).widget() is old_row),
            -1,
        )
        if index < 0 or not isinstance(getattr(layout, "_items", None), list):
            self.refresh_improvements()
            return
        scrollbar = self.improvement_scroll.verticalScrollBar()
        old_scroll = scrollbar.value()
        self.improvement_list_widget.setUpdatesEnabled(False)
        try:
            new_row = ImprovementRow(
                self.character,
                old_row.improvement,
                self.confirm_remove_improvement,
                self.edit_improvement_choices,
                self.confirm_remove_empowerment,
            )
            # The redesigned MainWindow supplies these optional enhancements.
            if hasattr(self, "style_redesign_improvement_row"):
                self.style_redesign_improvement_row(new_row)
            if hasattr(self, "enable_improvement_long_press_reorder"):
                self.enable_improvement_long_press_reorder(new_row)
            old_row.hide()
            removed_item = layout.takeAt(index)
            layout.addWidget(new_row)
            replacement_item = layout.takeAt(layout.count() - 1)
            layout._items.insert(index, replacement_item)
            old_row.setParent(None)
            old_row.deleteLater()
            del removed_item
            layout.invalidate()
            # Only the replacement row changed.  The redesigned MainWindow
            # can preserve the measured heights of cards in the opposite
            # column instead of re-measuring every open rich-text card.
            # Repeatedly re-measuring an already-open Spellcasting card was
            # what made its internal vertical spacing grow after toggling a
            # different card several times.
            try:
                self.refresh_improvement_scroll_geometry(
                    changed_widget=new_row,
                )
            except TypeError:
                # Compatibility with the older mixin implementation.
                self.refresh_improvement_scroll_geometry()
            scrollbar.setValue(min(old_scroll, scrollbar.maximum()))
        finally:
            self.improvement_list_widget.setUpdatesEnabled(True)
            self.improvement_list_widget.update()

    def refresh_improvements(self):
        # Link the companion note BEFORE rows are constructed/styled. The main
        # window adds its note marker during row styling, not during refresh_notes.
        if hasattr(self, "synchronize_animal_buddy_note"):
            self.synchronize_animal_buddy_note()
        if hasattr(self, "synchronize_mighty_note"):
            self.synchronize_mighty_note()
        used = self.character.progression.used_IP
        total = self.character.progression.current_IP

        self.count_box.setText(f"{used} / {total}")

        if hasattr(self, "add_improvement_btn"):
            browse_only = self.character.progression.available_IP <= 0
            self.add_improvement_btn.setText(
                "Browse Improvements"
                if browse_only
                else "+  Add Improvement"
            )

        free_used = len(self.character.free_heightened_ability_stats)
        free_total = self.character.free_heightened_ability_slots

        if free_total > 0:
            self.free_heightened_label.show()
            self.free_heightened_label.setText(
                f"Free Heightened: {free_used}/{free_total}  ✎"
            )
            self.free_heightened_label.setToolTip(
                "Click to add, remove, or reassign free Heightened Ability bonuses."
            )
        else:
            self.free_heightened_label.hide()

        set_themed_stylesheet(self.free_heightened_label, """
            QLabel {
                border: 1px solid #c79a3b;
                border-radius: 8px;
                background-color: #fffaf0;
                font-size: 11px;
                font-weight: 800;
                color: #6b4b14;
                padding: 4px 8px;
                margin: 0px;
            }
            QLabel:hover {
                background-color: #fff4df;
                border-color: #a87824;
                color: #25190f;
            }
        """)

        self.improvement_list_widget.setUpdatesEnabled(False)

        try:
            self.clear_layout(self.improvement_list_layout)

            # Free Heightened Ability choices are managed from the compact
            # header control above. They are intentionally NOT displayed as
            # Improvement cards.
            QApplication.sendPostedEvents(
                None,
                QEvent.Type.DeferredDelete,
            )

            ordered_improvements = [
                improvement
                for improvement in (
                    self.character.improvements.list_of_taken_improvements
                )
                if not (
                    improvement.cost == 0
                    and "heightened" in improvement.name.lower()
                )
            ]

            ordered_improvements.sort(
                key=lambda item: (
                    int(getattr(item, "sort_order", 0)),
                    item.name.lower(),
                )
            )

            skilled_at_improvements = [
                improvement
                for improvement in ordered_improvements
                if improvement.catalog_id == "skilled_at"
            ]

            paid_heightened = [item for item in ordered_improvements
                               if item.catalog_id == "heightened_ability"
                               and item.source == "ip"]
            heightened_added = False
            skilled_added = False

            for improvement in ordered_improvements:
                if improvement.catalog_id == "heightened_ability" and improvement.source == "ip":
                    if not heightened_added:
                        self.improvement_list_layout.addWidget(
                            PaidHeightenedAbilityGroup(self, paid_heightened)
                        )
                        heightened_added = True
                    continue
                if improvement.catalog_id == "skilled_at":
                    if skilled_added:
                        continue

                    skilled_added = True
                    self.improvement_list_layout.addWidget(
                        SkilledAtGroupRow(
                            skilled_at_improvements,
                            self.confirm_remove_improvement,
                            self.edit_improvement_choices,
                        )
                    )
                    continue

                self.add_improvement_row_to_layout(improvement)

        finally:
            self.improvement_list_widget.setUpdatesEnabled(True)
            self.improvement_list_widget.update()

        QTimer.singleShot(
            0,
            self.refresh_improvement_scroll_geometry,
        )

    def add_improvement_row_to_layout(self, improvement):
        row = ImprovementRow(
            self.character,
            improvement,
            self.confirm_remove_improvement,
            self.edit_improvement_choices,
            self.confirm_remove_empowerment,
        )
        self.improvement_list_layout.addWidget(row)

        if not improvement.expanded:
            return

    def refresh_improvement_scroll_geometry(self):
        if not hasattr(self, "improvement_scroll"):
            return

        layout = self.improvement_list_layout
        item_count = layout.count()

        if item_count == 0:
            self.improvement_scroll.hide()
            self.improvement_scroll.setFixedHeight(0)
            return

        self.improvement_scroll.show()

        # No visible vertical scrollbar: use the stable viewport width so
        # expanding a card cannot create or remove a scrollbar-sized gap.
        scroll_width = self.improvement_scroll.viewport().width()
        if scroll_width <= 0:
            scroll_width = self.improvement_scroll.width()
        content_width = max(1, scroll_width - 4)

        self.improvement_list_widget.setFixedWidth(
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

            row_layout = widget.layout()

            if (
                row_layout is not None
                and row_layout.hasHeightForWidth()
            ):
                row_height = row_layout.heightForWidth(
                    content_width
                )
            elif row_layout is not None:
                row_height = row_layout.minimumSize().height()
            else:
                row_height = widget.minimumSizeHint().height()

            # The cost circle is 42px tall, so a collapsed row
            # should never be shorter than that.
            # Nested wrapping QLabel heightForWidth can lag one layout pass.
            # Add a small safety margin for DPI rounding, especially for
            # two-line Empowerment rows; scrolling is preferable to clipping.
            row_height = max(42, row_height + (8 if isinstance(widget, ImprovementRow)
                and widget.improvement.expanded else 0))

            widget.setFixedHeight(row_height)

            content_height += row_height
            widget_count += 1

        if widget_count > 1:
            content_height += (
                layout.spacing() * (widget_count - 1)
            )

        margins = layout.contentsMargins()

        content_height += (
            margins.top()
            + margins.bottom()
        )

        self.improvement_list_widget.setFixedHeight(
            content_height
        )

        # ------------------------------------------------------------
        # Use all available vertical room in the Improvements column.
        # Only show scrolling once the list genuinely no longer fits.
        # ------------------------------------------------------------

        frame = self.improvement_scroll.parentWidget()
        parent_layout = frame.layout()

        frame_height = frame.height()

        frame_margins = parent_layout.contentsMargins()
        spacing = parent_layout.spacing()

        header_height = parent_layout.itemAt(0).sizeHint().height()

        add_button_height = self.add_improvement_btn.sizeHint().height()

        free_label_height = (
            self.free_heightened_label.sizeHint().height()
            if self.free_heightened_label.isVisible()
            else 0
        )

        # Extra visual gap between the end of the improvements
        # scroll area and the + button.
        scroll_bottom_gap = 10

        maximum_height = (
            frame_height
            - frame_margins.top()
            - frame_margins.bottom()
            - header_height
            - add_button_height
            - free_label_height
            - (spacing * 3)
            - scroll_bottom_gap
        )
        maximum_height = max(0, maximum_height)

        visible_height = min(content_height, maximum_height)
        self.improvement_scroll.setFixedHeight(visible_height)

        # Overflow is still scrollable by mouse wheel / trackpad. Hiding
        # the painted scrollbar does not disable its internal range.
        self.improvement_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.improvement_list_widget.updateGeometry()
        self.improvement_scroll.updateGeometry()

    def confirm_remove_improvement(self, improvement):
        if self.block_if_readonly():
            return

        if not ImprovementSystem.can_remove_heightened(self.character, improvement):
            return

        if not ask_yes_no(
            self,
            "Remove Improvement",
            (
                f"Remove {improvement.name} completely?\n\n"
                f"This will refund {improvement.total_cost()} IP."
            ),
        ):
            return

        removing_spellcasting = (
            improvement.catalog_id == "spellcasting"
        )

        removing_sneak_attack = (
            improvement.catalog_id == "sneak_attack"
        )

        self.character.improvements.remove(
            improvement.id
        )

        if removing_spellcasting:
            self.ensure_character_notes()

            self.character.notes.list_of_notes = [
                note
                for note in self.character.notes.list_of_notes
                if note.title.strip().lower() != "spellcasting verbs"
            ]

            if not self.character.notes.list_of_notes:
                self.notes_board_visible = False
                self.notes_frame.hide()

        if removing_sneak_attack:
            self.ensure_character_notes()

            self.character.notes.list_of_notes = [
                note
                for note in self.character.notes.list_of_notes
                if note.title.strip().lower() != "sneak attack"
            ]

            if not self.character.notes.list_of_notes:
                self.notes_board_visible = False
                self.notes_frame.hide()
        self.character.validate()

        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()


    def confirm_remove_skilled_at_group(
        self,
        skilled_improvements,
    ):
        if self.block_if_readonly():
            return

        skilled_improvements = [
            improvement
            for improvement in skilled_improvements
            if improvement.catalog_id == "skilled_at"
        ]

        if not skilled_improvements:
            return

        total_refund = sum(
            improvement.total_cost()
            for improvement in skilled_improvements
        )

        count = len(
            skilled_improvements
        )

        if not ask_yes_no(
            self,
            "Remove Skilled At",
            (
                "Remove Skilled At completely?\n\n"
                f"This will remove all {count} "
                f"Skilled At choice{'s' if count != 1 else ''} "
                f"and refund {total_refund} IP."
            ),
        ):
            return

        for improvement in list(
            skilled_improvements
        ):
            self.character.improvements.remove(
                improvement.id
            )

        self.character.validate()

        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()
    
    def confirm_remove_heightened_group(
        self,
        heightened_improvements,
    ):
        if self.block_if_readonly():
            return

        heightened_improvements = [
            improvement
            for improvement in heightened_improvements
            if improvement.catalog_id == "heightened_ability"
        ]

        if not heightened_improvements:
            return

        total_refund = sum(
            improvement.total_cost()
            for improvement in heightened_improvements
        )

        count = len(
            heightened_improvements
        )

        if not ask_yes_no(
            self,
            "Remove Heightened Ability",
            (
                "Remove Heightened Ability completely?\n\n"
                f"This will remove all {count} "
                f"Heightened Ability choice{'s' if count != 1 else ''} "
                f"and refund {total_refund} IP."
            ),
        ):
            return

        for improvement in list(
            heightened_improvements
        ):
            self.character.improvements.remove(
                improvement.id
            )

        self.character.validate()

        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()
    
    def edit_empowerment_choices_from_ui(self, improvement, empowerment):
        if self.block_if_readonly():
            return

        option = IMPROVEMENT_CATALOG.get(improvement.catalog_id)
        if option is None:
            return

        required_choices = []

        groups = option.get("empowerment_groups", {})

        group = groups.get(empowerment.group_id)
        if group is not None:
            for possible_option in group.get("options", []):
                if possible_option.get("id") == empowerment.catalog_id:
                    required_choices = possible_option.get("requires_choices", [])
                    break

        if not required_choices:
            return

        dialog = ChoiceInputDialog(
            required_choices,
            title=f"Edit {empowerment.name}",
            parent=self,
            initial_choices=empowerment.choices,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        empowerment.choices = dialog.choices

        self.character.validate()
        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()
        
    def edit_improvement_choices(self, improvement):
        if self.block_if_readonly():
            return

        # ============================================================
        # Custom improvement
        # ============================================================

        if improvement.catalog_id == "custom":
            old_cost = int(improvement.cost)

            # Capture this BEFORE opening the dialog.
            #
            # Example:
            # current custom cost = 3
            # available IP = 2
            #
            # Maximum edited cost = 5.
            available_before_edit = int(
                self.character.progression.available_IP
            )

            maximum_new_cost = min(
                10,
                old_cost + available_before_edit,
            )

            dialog = CustomImprovementDialog(
                parent=self,
                initial_name=improvement.name,
                initial_description=improvement.description,
                initial_cost=old_cost,
                initial_icon=(improvement.choices or {}).get("_custom_icon", ""),
                maximum_cost=maximum_new_cost,
                edit_mode=True,
            )

            if (
                dialog.exec()
                != QDialog.DialogCode.Accepted
            ):
                return

            edited = dialog.improvement

            if edited is None:
                return

            new_cost = int(
                edited["cost"]
            )

            # Extra defensive validation.
            # The QSpinBox already prevents this, but this protects
            # the model even if the dialog is changed later.
            if new_cost > maximum_new_cost:
                QMessageBox.warning(
                    self,
                    "Not Enough IP",
                    (
                        "The edited improvement would use more IP "
                        "than was available when editing began."
                    ),
                )
                return

            # --------------------------------------------------------
            # Apply all three editable values.
            # --------------------------------------------------------

            improvement.name = edited["name"]
            improvement.description = edited["description"]
            improvement.cost = new_cost
            improvement.choices["_custom_icon"] = edited.get("icon", "")

            self.character.validate()

            self.mark_dirty(auto_save=True)
            self.refresh_all()
            return

        # ============================================================
        # Normal catalog improvement
        # ============================================================

        option = ImprovementCatalogSystem.get_option(
            improvement.catalog_id
        )

        if option is None:
            return

        required_choices = option.get(
            "requires_choices",
            [],
        )

        if not required_choices:
            # A double-click on a non-editable catalog Improvement is a no-op.
            return

        dialog = ChoiceInputDialog(
            required_choices,
            title=f"Edit {improvement.name}",
            parent=self,
            initial_choices=improvement.choices,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        previous_damage = (improvement.choices or {}).get("_buddy_marked_damage")
        improvement.choices = dialog.choices
        if improvement.catalog_id == "animal_buddy" and previous_damage is not None:
            improvement.choices["_buddy_marked_damage"] = previous_damage

        option = ImprovementCatalogSystem.get_option(
            improvement.catalog_id
        )

        if option is not None:
            improvement.name = (
                ImprovementSystem
                .format_improvement_name(
                    option,
                    improvement.choices,
                )
            )

        self.character.validate()

        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()

    def edit_empowerment_choices(self, parent_improvement, empowerment):
        if self.block_if_readonly():
            return
        
        required_choices = self.get_empowerment_required_choices(
            parent_improvement,
            empowerment,
        )

        if not required_choices:
            QMessageBox.information(
                self,
                "No Choices",
                "This empowerment does not have editable choices."
            )
            return

        dialog = ChoiceInputDialog(
            required_choices,
            title=f"Edit {empowerment.name}",
            parent=self,
            initial_choices=empowerment.choices,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        empowerment.choices = dialog.choices

        self.character.validate()
        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()

    def get_empowerment_required_choices(self, parent_improvement, empowerment):
        if (
            parent_improvement.catalog_id == "born_of_soil"
            and empowerment.catalog_id == "additional_attuned_land"
        ):
            return ["attuned_land", "attuned_land_description"]
        
        parent_option = ImprovementCatalogSystem.get_option(
            parent_improvement.catalog_id
        )

        if parent_option is None:
            return []

        groups = parent_option.get("empowerment_groups", {})
        group = groups.get(empowerment.group_id)

        if group is None:
            return []

        if group.get("requires_choices"):
            return group.get("requires_choices", [])

        empowerment_catalog_id = empowerment.catalog_id

        for option in group.get("options", []):
            option_id = option.get("id", "")

            if empowerment_catalog_id == option_id:
                return option.get("requires_choices", [])

            if empowerment_catalog_id.startswith(option_id + "_"):
                return option.get("requires_choices", [])

        return []
            
    def is_scaling_empowerment(self, parent_improvement, empowerment):
        option = ImprovementCatalogSystem.get_option(
            parent_improvement.catalog_id
        )

        if option is None:
            return False

        scaling_groups = option.get("scaling_empowerments", {})

        return empowerment.group_id in scaling_groups

    def confirm_remove_empowerment(self, improvement, empowerment):
        if self.block_if_readonly():
            return

        if not ask_yes_no(
            self,
            "Remove Empowerment",
            f"Remove '{empowerment.name}'?"
        ):
            return

        success = ImprovementSystem.remove_empowerment(
            self.character,
            improvement.id,
            empowerment.id,
        )

        if not success:
            QMessageBox.warning(
                self,
                "Cannot Remove Empowerment",
                "Could not remove this empowerment.",
            )
            return
        
        # If Sneak Attack is stored in a note, keep that note synchronized
        # with the empowerments that still exist.
        if (
            improvement.catalog_id == "sneak_attack"
            and improvement.choices.get("_sneak_attack_note_created")
        ):
            sneak_attack_note = self.find_note_by_title(
                "Sneak Attack"
            )

            if sneak_attack_note is not None:
                sneak_attack_note.text = (
                    self.build_sneak_attack_note_text(
                        improvement
                    )
                )
        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()


    def confirm_remove_scaling_level(self, improvement):
        if self.block_if_readonly():
            return

        option = ImprovementCatalogSystem.get_option(
            improvement.catalog_id
        )

        if option is None:
            return

        if option.get("purchase_rule") != "repeatable_scaling":
            return

        times_taken = getattr(
            improvement,
            "times_taken",
            1,
        )

        if times_taken <= 1:
            return

        base_cost = int(
            option.get("base_cost", 0)
        )

        cost_increase = int(
            option.get("cost_increase", 0)
        )

        refund = (
            base_cost
            + ((times_taken - 1) * cost_increase)
        )

        if not ask_yes_no(
            self,
            "Remove Improvement Level",
            (
                f"Remove the highest level of "
                f"{improvement.name}?\n\n"
                f"Refund: {refund} IP"
            ),
        ):
            return

        success = ImprovementSystem.remove_improvement(
            self.character,
            improvement.id,
        )

        if not success:
            return

        self.mark_dirty(auto_save=True)
        self.refresh_after_improvement_change()


    def manage_free_heightened_abilities_from_ui(self):
        if self.block_if_readonly():
            return

        free_total = int(
            self.character.free_heightened_ability_slots
        )

        if free_total <= 0:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Heightened Abilities")
        dialog.setMinimumWidth(390)

        set_themed_stylesheet(
            dialog,
            FANTASY_DIALOG_QSS,
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Heightened Abilities")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_themed_stylesheet(
            title,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 19px;
                font-weight: 900;
                color: #25190f;
            }
            """,
        )
        layout.addWidget(title)

        summary = QLabel()
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary.setWordWrap(True)
        set_themed_stylesheet(
            summary,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 12px;
                font-weight: 700;
                color: #765d34;
            }
            """,
        )
        layout.addWidget(summary)

        rows = {}

        for stat_name in STAT_NAMES:
            row = QHBoxLayout()
            row.setSpacing(8)

            name_label = QLabel(stat_name.title())
            set_themed_stylesheet(
                name_label,
                """
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: Georgia;
                    font-size: 14px;
                    font-weight: 800;
                    color: #25190f;
                }
                """,
            )

            minus_btn = QPushButton("−")
            minus_btn.setFixedSize(34, 30)
            make_negative_button(minus_btn)
            set_themed_stylesheet(minus_btn, minus_btn.styleSheet() + """
                QPushButton:disabled {
                    color: #aaa397;
                    background-color: #eee9df;
                    border: 1px solid #d9cdb7;
                }
            """)

            value_label = QLabel("0")
            value_label.setFixedWidth(48)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            set_themed_stylesheet(
                value_label,
                """
                QLabel {
                    background-color: #fffaf0;
                    border: 1px solid #d9bd82;
                    border-radius: 8px;
                    font-family: Georgia;
                    font-size: 14px;
                    font-weight: 900;
                    color: #25190f;
                    padding: 4px;
                }
                """,
            )

            plus_btn = QPushButton("+")
            plus_btn.setFixedSize(34, 30)
            make_positive_button(plus_btn)

            row.addWidget(name_label, 1)
            row.addWidget(minus_btn)
            row.addWidget(value_label)
            row.addWidget(plus_btn)
            layout.addLayout(row)

            rows[stat_name] = (
                minus_btn,
                value_label,
                plus_btn,
            )

        info = QLabel(
            "Use two slots for two different +1 abilities for free, "
            "or the same ability twice for +2 at a cost of 1 IP."
        )
        info.setWordWrap(True)
        set_themed_stylesheet(
            info,
            """
            QLabel {
                background: transparent;
                border: none;
                font-family: Georgia;
                font-size: 11px;
                font-weight: 600;
                color: #765d34;
            }
            """,
        )
        layout.addWidget(info)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Done")
        make_positive_button(close_btn)
        close_btn.setFixedSize(92, 34)
        close_btn.clicked.connect(dialog.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        def refresh_manager():
            used = len(
                self.character.free_heightened_ability_stats
            )
            total = int(
                self.character.free_heightened_ability_slots
            )
            available_ip = int(
                self.character.progression.available_IP
            )

            summary.setText(
                f"Free selections used: {min(used, total)} / {total}"
                + (
                    f"   •   Available IP: {available_ip}"
                    if available_ip >= 0
                    else ""
                )
            )

            counts = {
                stat_name: self.character.free_heightened_ability_stats.count(
                    stat_name
                )
                for stat_name in STAT_NAMES
            }

            has_free_slot = used < total

            for stat_name, (
                minus_btn,
                value_label,
                plus_btn,
            ) in rows.items():
                count = counts[stat_name]
                value_label.setText(
                    f"+{count}" if count else "—"
                )
                can_remove_free = count > 0 and self.character.stats.get_stat(stat_name).bonus == count
                minus_btn.setEnabled(can_remove_free)
                minus_btn.setToolTip("Remove paid tiers first" if count and not can_remove_free else "Remove free bonus")

                can_add = used < total and self.character.stats.get_stat(stat_name).bonus == count and count <= available_ip
                plus_btn.setEnabled(can_add)
                plus_btn.setToolTip(
                    (f"Use a free slot to raise to +{count + 1} for {count} IP" if count else "Add a free +1 bonus") if can_add
                    else "Use Add Improvement for paid Heightened Abilities."
                )

        def add_stat(stat_name):
            before = list(
                self.character.free_heightened_ability_stats
            )

            if not StatSystem.add_free_heightened_ability(
                self.character,
                stat_name,
            ):
                return

            if before == self.character.free_heightened_ability_stats:
                return

            self.mark_dirty(auto_save=True)
            self.refresh_after_improvement_change()
            refresh_manager()

        def remove_stat(stat_name):
            if not StatSystem.remove_free_heightened_ability(
                self.character,
                stat_name,
            ):
                return

            self.mark_dirty(auto_save=True)
            self.refresh_after_improvement_change()
            refresh_manager()

        for stat_name, (
            minus_btn,
            _value_label,
            plus_btn,
        ) in rows.items():
            minus_btn.clicked.connect(
                lambda checked=False, name=stat_name:
                    remove_stat(name)
            )
            plus_btn.clicked.connect(
                lambda checked=False, name=stat_name:
                    add_stat(name)
            )

        refresh_manager()
        dialog.exec()

    def add_free_heightened_ability_from_ui(self):
        self.manage_free_heightened_abilities_from_ui()

    def remove_free_heightened_ability_from_ui(self, stat_name):
        if self.block_if_readonly():
            return
        
        success = StatSystem.remove_free_heightened_ability(
            self.character,
            stat_name,
        )

        if not success:
            return

        self.mark_dirty(auto_save=True)
        self.refresh_all()
