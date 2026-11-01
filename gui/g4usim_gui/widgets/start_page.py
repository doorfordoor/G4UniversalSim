"""Start page: new simulation, recent projects and the examples gallery."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core import examples, icons
from g4usim_gui.core.i18n import ui_text, ui_format
from g4usim_gui.core.accessibility import name_control
from g4usim_gui.core.theme import current_colors, on_accent

THUMB = QSize(320, 200)


class ExampleCard(QFrame):
    clicked = Signal(str)

    def __init__(self, example: examples.Example, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.example = example
        self.setProperty("uiRole", "card")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)   # cards of a row share its height
        self.setAccessibleName(example.title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.thumbnail = QLabel()
        self.thumbnail.setProperty("uiRole", "thumbnail")
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setFixedHeight(THUMB.height() * 3 // 4)
        self.thumbnail.setMinimumWidth(200)
        path = example.thumbnail()
        if path.is_file():
            pixmap = QPixmap(str(path))
            self.thumbnail.setPixmap(pixmap.scaled(QSize(THUMB.width() * 3 // 4, THUMB.height() * 3 // 4),
                                                   Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.thumbnail.setText("No bundled results")
        self.title = QLabel(example.title)
        self.title.setProperty("uiRole", "cardTitle")
        self.summary = QLabel(example.summary)
        self.summary.setProperty("uiRole", "hint")
        self.summary.setWordWrap(True)
        self.summary.setMinimumHeight(54)
        self.summary.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for tag in example.tags:
            label = QLabel(tag)
            label.setProperty("uiRole", "tag")
            tags.addWidget(label)
        tags.addStretch(1)
        self.open_button = QPushButton("Open example")
        self.open_button.clicked.connect(lambda: self.clicked.emit(example.id))
        footer = QHBoxLayout()
        footer.addLayout(tags, 1)
        footer.addWidget(self.open_button)
        layout.addWidget(self.thumbnail)
        layout.addWidget(self.title)
        layout.addWidget(self.summary, 1)
        layout.addLayout(footer)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.example.id)
        super().mouseReleaseEvent(event)


class StartPage(QWidget):
    blankSimulationRequested = Signal()
    newSimulationRequested = Signal()
    openProjectRequested = Signal()
    recentProjectRequested = Signal(str)
    exampleRequested = Signal(str)
    environmentRequested = Signal()
    importBundleRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        scroll = QScrollArea()
        self.start_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self.start_content = content
        content.setObjectName("pageViewport")
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setProperty("uiRole", "hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(18)
        self.logo = QLabel()
        self.logo.setFixedSize(56, 56)
        hero_layout.addWidget(self.logo, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(6)
        title = QLabel("Welcome to G4UniversalSim")
        title.setProperty("uiRole", "heroTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Set up a Geant4 simulation step by step, run it and look at the results, "
                          "or start from one of the examples below.")
        subtitle.setProperty("uiRole", "hint")
        subtitle.setWordWrap(True)
        self.start_actions_layout = QGridLayout()
        self.start_actions_layout.setSpacing(10)
        self.blank_button = QPushButton("New blank simulation")
        self.blank_button.clicked.connect(self.blankSimulationRequested)
        self.blank_button.setProperty("buttonRole", "primary")
        self.new_button = QPushButton("Create from template...")
        self.open_button = QPushButton("Open project...")
        self.import_button = QPushButton(ui_text("Import configuration bundle..."))
        self.environment_button = QPushButton(ui_text("Environment setup..."))
        self.import_button.clicked.connect(self.importBundleRequested)
        self.environment_button.clicked.connect(self.environmentRequested)
        self.start_actions = (self.blank_button, self.new_button, self.open_button, self.import_button, self.environment_button)
        for button in self.start_actions:
            button.setIconSize(QSize(16, 16))
            button.setMinimumHeight(34)
        self._action_columns = 0
        text.addWidget(title)
        text.addWidget(subtitle)
        text.addSpacing(6)
        text.addLayout(self.start_actions_layout)
        self.keyboard_hint = QLabel(ui_text("Keyboard: Ctrl+Alt+1–9 pages; F6 next region; Shift+F6 previous region; Ctrl+Alt+E environment setup."))
        self.keyboard_hint.setWordWrap(True)
        self.keyboard_hint.setProperty("uiRole", "hint")
        text.addWidget(self.keyboard_hint)
        hero_layout.addLayout(text, 1)

        recent_box = QFrame()
        recent_box.setProperty("uiRole", "hero")
        recent_layout = QVBoxLayout(recent_box)
        recent_layout.setContentsMargins(18, 16, 18, 16)
        recent_layout.setSpacing(4)
        recent_title = QLabel("Recent projects")
        recent_title.setProperty("uiRole", "sectionTitle")
        recent_layout.addWidget(recent_title)
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(2)
        recent_layout.addLayout(self.recent_list)
        recent_layout.addStretch(1)
        recent_box.setMinimumWidth(300)

        top = QBoxLayout(QBoxLayout.LeftToRight)
        self.start_top_layout = top
        self.start_hero = hero
        top.setSpacing(18)
        top.addWidget(hero, 3)
        top.addWidget(recent_box, 2)
        layout.addLayout(top)

        gallery_title = QLabel("Examples")
        gallery_title.setProperty("uiRole", "sectionTitle")
        gallery_hint = QLabel("Each example opens with results Geant4 has already computed; "
                              "press Generate & Run on the Configuration page to compute them again.")
        gallery_hint.setProperty("uiRole", "hint")
        gallery_hint.setWordWrap(True)
        layout.addWidget(gallery_title)
        layout.addWidget(gallery_hint)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.cards: list[ExampleCard] = []
        for example in examples.EXAMPLES:
            card = ExampleCard(example)
            card.clicked.connect(self.exampleRequested)
            self.cards.append(card)
        self._columns = 0
        layout.addLayout(self.grid)
        layout.addStretch(1)

        self.new_button.clicked.connect(self.newSimulationRequested)
        self.open_button.clicked.connect(self.openProjectRequested)
        self.set_recent_projects([])
        self.refresh_theme()
        self._adapt_start_layout()
        self._refresh_start_accessibility()

    def set_recent_projects(self, paths: list[str]) -> None:
        self._recent = list(paths)
        while self.recent_list.count():
            widget = self.recent_list.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)   # gone at once, not only after the deferred delete
                widget.deleteLater()
        if not paths:
            empty = QLabel(ui_text("No recent projects yet. Saved projects appear here."))
            empty.setProperty("uiRole", "hint")
            empty.setWordWrap(True)
            self.recent_list.addWidget(empty)
            return
        for path in paths[:6]:
            button = QPushButton(Path(path).stem)
            button.setProperty("buttonRole", "link")
            button.setToolTip(path)
            button.setAccessibleName(ui_format("Open recent project {name}", name=Path(path).stem))
            button.setAccessibleDescription(path)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, p=path: self.recentProjectRequested.emit(p))
            self.recent_list.addWidget(button)

    def refresh_language(self) -> None:
        self.set_recent_projects(self._recent)
        self.import_button.setText(ui_text("Import configuration bundle..."))
        self.environment_button.setText(ui_text("Environment setup..."))
        self.keyboard_hint.setText(ui_text("Keyboard: Ctrl+Alt+1–9 pages; F6 next region; Shift+F6 previous region; Ctrl+Alt+E environment setup."))
        self._refresh_start_accessibility()
        self._adapt_start_layout()

    def _refresh_start_accessibility(self):
        for button, key in zip(self.start_actions, (
                "New blank simulation", "Create from template...", "Open project...",
                "Import configuration bundle...", "Environment setup...")):
            name_control(button, key)
        self.environment_button.setAccessibleDescription(ui_text(
            "Discover and choose an environment. Installation is available in that dialog; opening it does not run or install anything."))
        for card in self.cards:
            card.setAccessibleName(ui_text(card.example.title))
            card.open_button.setAccessibleName(ui_format("Open example {name}", name=ui_text(card.example.title)))

    def adapt_to_width(self, width: int):
        # The containing dock host can be wider than the actual desktop viewport.
        # Use the shell's budget to break the minimum-size/column-count cycle.
        self._available_width = max(260, width)
        self.start_content.setMaximumWidth(self._available_width)
        self._adapt_start_layout()

    def _adapt_start_layout(self):
        budget = min(self.width(), getattr(self, '_available_width', self.width()))
        self.start_top_layout.setDirection(QBoxLayout.TopToBottom if budget < 1100 else QBoxLayout.LeftToRight)
        available = max(1, min(self.start_hero.width() - 130, budget - 180))
        button_width = max(button.sizeHint().width() for button in self.start_actions)
        columns = max(1, min(3, (available + 10) // (button_width + 10)))
        if columns != self._action_columns:
            while self.start_actions_layout.count():
                self.start_actions_layout.takeAt(0)
            for index, button in enumerate(self.start_actions):
                self.start_actions_layout.addWidget(button, index // columns, index % columns)
            for column in range(3):
                self.start_actions_layout.setColumnStretch(column, 1 if column < columns else 0)
            self._action_columns = columns
        self._reflow_gallery(budget)

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.logo.setPixmap(icons.pixmap("logo", colors.accent, 56))
        self.new_button.setIcon(icons.icon("plus", on_accent(colors), 16))
        self.open_button.setIcon(icons.icon("open", colors.text, 16))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._adapt_start_layout()

    def _reflow_gallery(self, budget):
        columns = max(1, min(3, (min(self.start_scroll.viewport().width(), budget) - 56) // 340))
        if columns != self._columns:
            self._columns = columns
            for card in self.cards:
                self.grid.removeWidget(card)
            for index, card in enumerate(self.cards):
                self.grid.addWidget(card, index // columns, index % columns)
            for column in range(3):
                self.grid.setColumnStretch(column, 1 if column < columns else 0)
