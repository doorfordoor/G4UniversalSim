"""Start page: new simulation, recent projects and the examples gallery."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
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
from g4usim_gui.core.i18n import ui_text
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
    newSimulationRequested = Signal()
    openProjectRequested = Signal()
    recentProjectRequested = Signal(str)
    exampleRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
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
        subtitle = QLabel("Set up a Geant4 simulation step by step, run it and look at the results, "
                          "or start from one of the examples below.")
        subtitle.setProperty("uiRole", "hint")
        subtitle.setWordWrap(True)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.new_button = QPushButton("New simulation...")
        self.new_button.setProperty("buttonRole", "primary")
        self.open_button = QPushButton("Open project...")
        for button in (self.new_button, self.open_button):
            button.setIconSize(QSize(16, 16))
            button.setMinimumHeight(34)
            actions.addWidget(button)
        actions.addStretch(1)
        text.addWidget(title)
        text.addWidget(subtitle)
        text.addSpacing(6)
        text.addLayout(actions)
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

        top = QHBoxLayout()
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
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, p=path: self.recentProjectRequested.emit(p))
            self.recent_list.addWidget(button)

    def refresh_language(self) -> None:
        self.set_recent_projects(self._recent)

    def refresh_theme(self) -> None:
        colors = current_colors()
        self.logo.setPixmap(icons.pixmap("logo", colors.accent, 56))
        self.new_button.setIcon(icons.icon("plus", on_accent(colors), 16))
        self.open_button.setIcon(icons.icon("open", colors.text, 16))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        columns = max(1, min(3, (self.width() - 56) // 340))
        if columns != self._columns:
            self._columns = columns
            for card in self.cards:
                self.grid.removeWidget(card)
            for index, card in enumerate(self.cards):
                self.grid.addWidget(card, index // columns, index % columns)
            for column in range(3):
                self.grid.setColumnStretch(column, 1 if column < columns else 0)
