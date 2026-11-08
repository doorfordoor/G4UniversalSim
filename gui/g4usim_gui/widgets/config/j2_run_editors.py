"""Structured J2 rows; the containing page owns F5 transactions and models."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from uuid import uuid4

from PySide6.QtCore import Signal, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QLineEdit, QComboBox, QCheckBox, QPushButton, QLabel, QTabWidget,
    QScrollArea, QAbstractItemView)

from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.run_editor_model import (
    GPSDefinition, RegionDefinition, FieldDefinition, BiasRuleDefinition, ENUMS,
    MODULES, source_values,
)

# Stable field tokens are object names; labels are natural-language i18n keys.
FIELD_LABELS = {
    "editor_id": "Source editor identity (read only)", "name": "Name (blank for a global field)",
    "intensity": "Relative source intensity", "particle": "Particle name", "ion_z": "Ion atomic number Z",
    "ion_a": "Ion mass number A", "ion_charge": "Ion charge", "ion_excitation": "Ion excitation energy",
    "energy_type": "Energy distribution", "energy": "Energy / Gaussian mean", "energy_sigma": "Energy standard deviation",
    "energy_min": "Minimum energy", "energy_max": "Maximum energy", "alpha": "Power-law exponent",
    "ezero": "Exponential spectrum energy scale", "spectrum_file": "Spectrum file", "position_type": "Position sampling type",
    "shape": "Sampling shape", "center": "Position / center (three components and length unit)", "radius": "Radius",
    "inner_radius": "Inner radius", "halfx": "Half X", "halfy": "Half Y", "halfz": "Half Z",
    "beam_sigma": "Radial beam standard deviation", "beam_sigma_x": "Beam X standard deviation", "beam_sigma_y": "Beam Y standard deviation",
    "rot1": "First position rotation axis", "rot2": "Second position rotation axis", "confine": "Confining physical volume",
    "angular": "Angular distribution", "direction": "Direction / distribution axis", "min_theta": "Minimum polar angle",
    "max_theta": "Maximum polar angle", "angular_sigma": "Angular standard deviation", "angular_sigma_x": "Angular X standard deviation",
    "angular_sigma_y": "Angular Y standard deviation", "focus": "Focus (three components and length unit)",
    "volumes": "Volume names (comma separated)", "gamma": "Gamma production cut", "electron": "Electron production cut",
    "positron": "Positron production cut", "proton": "Proton production cut", "max_step": "Maximum step (charged particles by default)",
    "max_track_length": "Maximum total track length since creation", "max_time": "Maximum flight time",
    "min_kinetic_energy": "Minimum kinetic energy at step start", "magnetic": "Uniform magnetic field (vector and unit)",
    "electric": "Uniform electric field (vector and unit)", "magnetic_map": "Magnetic field CSV map", "electric_map": "Electric field CSV map",
    "min_step": "Minimum integration step", "delta_chord": "Chord tolerance", "delta_one_step": "Single-step tolerance",
    "delta_intersection": "Intersection tolerance", "process": "Process name (case sensitive)", "enabled": "Enable rule",
    "factor": "Cross-section bias factor", "only_primary": "Primary particles only", "apply_to_secondaries": "Apply to secondaries",
    "min_weight": "Minimum weight", "max_interactions": "Maximum interactions (-1 for unlimited)",
    "extra_modules": "Additional constructors", "replace_modules": "Replacement constructors", "manual_modules": "Manual constructors",
}


class StructuredRowsEditor(QWidget):
    """Selection is view state. Only a field edit or structure action emits."""
    changed = Signal()

    def __init__(self, row_type, key: str, parent=None):
        super().__init__(parent)
        self.row_type, self.key = row_type, key
        self.rows = []
        self._projecting = False
        self.controls = {}
        self.labels = {}
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName(f"j2.{key}.selection")
        self.list.setMaximumHeight(130)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        for action in ("Add", "Duplicate", "Remove", "Move up", "Move down"):
            button = QPushButton(ui_text(action))
            button.setObjectName(f"j2.{key}.{action.lower().replace(' ', '_')}")
            button.clicked.connect(lambda checked=False, a=action: self._structure(a))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        content = QWidget()
        self.form = QFormLayout(content)
        for f in fields(row_type):
            default = getattr(row_type(),f.name)
            if isinstance(default,bool):
                control = QCheckBox()
                control.toggled.connect(lambda checked, name=f.name: self._edit(name,checked))
            elif row_type is GPSDefinition and f.name in ENUMS:
                control = QComboBox()
                control.addItems(ENUMS[f.name])
                control.currentTextChanged.connect(lambda text, name=f.name: self._edit(name,text))
            else:
                control = QLineEdit()
                if f.name == "editor_id": control.setReadOnly(True)
                control.textChanged.connect(lambda text, name=f.name: self._edit(name,text))
            control.setObjectName(f"j2.{key}.{f.name}")
            label = QLabel(ui_text(FIELD_LABELS[f.name]))
            label.setBuddy(control)
            self.controls[f.name] = control
            self.labels[f.name] = label
            self.form.addRow(label,control)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll,1)
        self.list.currentRowChanged.connect(self._select)
        self._select(-1)

    @property
    def rows(self):
        owner = getattr(self, '_history_owner', None)
        if owner is None:
            return self._rows
        snapshot = owner.run_path_snapshot()
        model = snapshot.project.sourceEditor if self.key=='gps_sources' else snapshot.project.physicsEditor
        return getattr(model,self.key)

    @rows.setter
    def rows(self, value):
        if getattr(self, '_history_owner', None) is None:
            self._rows = value

    def refresh_reference(self):
        owner = getattr(self, '_history_owner', None)
        index = self.list.currentRow()
        self._row_reference = None
        if owner is not None and 0 <= index < len(self.rows):
            from g4usim_gui.core.sps_edit_model import row_reference
            self._row_reference = row_reference(owner.run_path_snapshot(),self.key,index,owner._edit_session.revision)

    def set_rows(self, rows):
        selected = self.list.currentRow()
        identity = (self.rows[selected].editor_id if self.row_type is GPSDefinition and 0 <= selected < len(self.rows) else None)
        self.rows = deepcopy(rows)
        if identity:
            selected = next((index for index,row in enumerate(self.rows) if row.editor_id == identity),selected)
        self._refresh_list(selected)

    def _title(self,row):
        if isinstance(row,BiasRuleDefinition): return row.particle + " / " + row.process
        return row.name or ui_text("Global field")

    def _refresh_list(self,selected):
        self.list.blockSignals(True)
        try:
            self.list.clear()
            self.list.addItems([self._title(row) for row in self.rows])
            self.list.setCurrentRow(min(max(selected,0),len(self.rows)-1))
        finally:
            self.list.blockSignals(False)
        self._select(self.list.currentRow())

    def _select(self,index):
        self._projecting = True
        try:
            for name,control in self.controls.items():
                control.setEnabled(index >= 0)
                if index < 0: continue
                value = getattr(self.rows[index],name)
                if isinstance(control,QCheckBox): control.setChecked(value)
                elif isinstance(control,QComboBox):
                    if control.findText(value) < 0: control.addItem(value)
                    control.setCurrentText(value)
                else: control.setText(value)
            self._active_fields(index)
            self.refresh_reference()
        finally:
            self._projecting = False

    def _active_fields(self,index):
        if index < 0 or self.row_type is not GPSDefinition: return
        row = self.rows[index]
        active = set(source_values(row)) | {"editor_id", "name", "intensity", "energy_type", "position_type", "angular", "center"}
        if row.position_type != "point": active.add("shape")
        if row.position_type == "volume": active.add("confine")
        if row.particle == "ion": active.update(("ion_z","ion_a","ion_charge","ion_excitation"))
        for name,control in self.controls.items():
            visible = name in active
            control.setVisible(visible)
            self.labels[name].setVisible(visible)

    def _edit(self,name,value):
        index = self.list.currentRow()
        if self._projecting or index < 0: return
        if name == 'editor_id':
            return
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            ref = self._row_reference
            if ref is None:
                return
            owner.edit_sps(action={'kind':'row','key':self.key,'op':'set','index':ref['index'],
                'field':name,'value':value,'reference':deepcopy(ref),'revision':ref['revision']})
            return
        setattr(self.rows[index],name,value)
        self.list.item(index).setText(self._title(self.rows[index]))
        self._active_fields(index)
        self.changed.emit()

    def _structure(self,action):
        index = self.list.currentRow()
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            op = {'Add':'add','Duplicate':'duplicate','Remove':'remove','Move up':'move','Move down':'move'}[action]
            if index < 0 and op in ('remove','move'):
                return
            if op=='duplicate' and index < 0:
                op='add'
            target=index+(-1 if action=='Move up' else 1)
            if op=='move' and not 0<=target<len(self.rows):
                return
            ref = deepcopy(getattr(self,'_row_reference',None))
            request={'kind':'row','key':self.key,'op':op,'index':index,
                'revision':owner._edit_session.revision if op=='add' else ref['revision'],
                'reference':ref,'target':target}
            if self.key=='gps_sources' and op in ('add','duplicate'):
                request['new_id']=uuid4().hex
            owner.edit_sps(action=request)
            return
        if action == "Remove":
            if index < 0: return
            del self.rows[index]
        elif action in ("Move up", "Move down"):
            target = index + (-1 if action == "Move up" else 1)
            if index < 0 or not 0 <= target < len(self.rows): return
            self.rows[index],self.rows[target] = self.rows[target],self.rows[index]
            index = target
        else:
            row = deepcopy(self.rows[index]) if action == "Duplicate" and index >= 0 else self.row_type()
            if isinstance(row,GPSDefinition) and action == "Duplicate": row.editor_id = uuid4().hex
            if hasattr(row,"name") and self.row_type is not BiasRuleDefinition:
                used = {x.name.lower() for x in self.rows}
                base = row.name or ("local" if self.rows else "")
                name, count = base, 2
                while name.lower() in used:
                    name, count = (base or "local")+str(count), count+1
                row.name = name
            self.rows.append(row)
            index = len(self.rows)-1
        self._refresh_list(index)
        self.changed.emit()

    def collect_current_row(self):
        """Capture controls even when a caller used setText without textEdited."""
        if getattr(self, '_history_owner', None) is not None:
            return
        index = self.list.currentRow()
        if index < 0: return
        row = self.rows[index]
        for name,control in self.controls.items():
            if name == "editor_id": continue  # immutable identity, never a draft
            if isinstance(control,QCheckBox): value = control.isChecked()
            elif isinstance(control,QComboBox): value = control.currentText()
            else: value = control.text()
            setattr(row,name,value)


class ModuleListEditor(QWidget):
    changed = Signal()

    def __init__(self,key,parent=None):
        super().__init__(parent)
        self.key = key
        self.values = []
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setMaximumHeight(95)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setObjectName(f"j2.{key}.list")
        layout.addWidget(self.list)
        self.choice = QComboBox()
        self.choice.addItems(sorted(MODULES))
        self.choice.setObjectName(f"j2.{key}.choice")
        layout.addWidget(self.choice)
        buttons = QHBoxLayout()
        for action in ("Add","Remove"):
            button = QPushButton(ui_text(action))
            button.setObjectName(f"j2.{key}.{action.lower()}")
            button.clicked.connect(lambda checked=False,a=action:self._change(a))
            buttons.addWidget(button)
        layout.addLayout(buttons)

    @property
    def values(self):
        owner = getattr(self,'_history_owner',None)
        return getattr(owner.run_path_snapshot().project.physicsEditor,self.key) if owner is not None else self._values

    @values.setter
    def values(self,value):
        if getattr(self,'_history_owner',None) is None:
            self._values=value

    def set_values(self,values):
        self.values = list(values)
        self.list.clear()
        self.list.addItems(values)

    def _change(self,action):
        owner=getattr(self,'_history_owner',None)
        if owner is not None:
            if action=='Remove' and self.list.currentRow()<0:
                return
            owner.edit_sps(action={'kind':'module','key':self.key,'op':action.lower(),
                'value':self.choice.currentText(),'index':self.list.currentRow(),'revision':owner._edit_session.revision})
            return
        values = list(self.values)
        if action == "Add": values.append(self.choice.currentText())
        elif self.list.currentRow() >= 0: del values[self.list.currentRow()]
        else: return
        self.set_values(values)
        self.changed.emit()


class J2RunEditors(QWidget):
    changed = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self._projecting = False
        layout = QVBoxLayout(self)
        self.hint = QLabel(ui_text("experimental editors: configuration drafts are not runtime or physical validation. Named sources replace the legacy source form; preview remains limited to its original subset."))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.multiple_vertex = QCheckBox(ui_text("Emit all named sources in each event (otherwise select by intensity)"))
        self.multiple_vertex.setObjectName("j2.source.multiple_vertex")
        self.multiple_vertex.toggled.connect(lambda value: self._top('source.multiple_vertex',value))
        layout.addWidget(self.multiple_vertex)
        self.intensity_hint = QLabel(ui_text("Simultaneous mode emits one vertex per source with primary weight 1. Intensity is retained only for switching back to random source selection."))
        self.intensity_hint.setWordWrap(True)
        layout.addWidget(self.intensity_hint)
        replay = QFormLayout()
        self.phase_space_file = QLineEdit()
        self.phase_space_file.setObjectName("j2.source.phase_space_file")
        self.phase_space_file.textChanged.connect(lambda value: self._top('source.phase_space_file',value))
        self.phase_space_recycle = QCheckBox(ui_text("Recycle phase-space histories"))
        self.phase_space_recycle.setObjectName("j2.source.phase_space_recycle")
        self.phase_space_recycle.toggled.connect(lambda value: self._top('source.phase_space_recycle',value))
        replay.addRow(ui_text("Phase-space replay files (comma separated)"),self.phase_space_file)
        replay.addRow(self.phase_space_recycle)
        layout.addLayout(replay)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs,1)
        self.observation = QLabel(ui_text("Planned configuration only. Backend application: not observed. Inspect current-run EffectiveConfig receipts separately."))
        self.observation.setWordWrap(True)
        layout.addWidget(self.observation)
        self.row_editors = {}
        for key,row_type,title in (("gps_sources",GPSDefinition,"Named GPS sources"),
                                   ("regions",RegionDefinition,"Region cuts and limits"),
                                   ("fields",FieldDefinition,"Fields"),
                                   ("bias_rules",BiasRuleDefinition,"Process bias rules")):
            editor = StructuredRowsEditor(row_type,key)
            self.row_editors[key] = editor
            editor.changed.connect(self._changed)
            self.tabs.addTab(editor,ui_text(title))
        self.modules = {}
        module_page = QWidget()
        module_layout = QHBoxLayout(module_page)
        for key in ("extra_modules","replace_modules","manual_modules"):
            column = QWidget()
            column_layout = QVBoxLayout(column)
            column_layout.addWidget(QLabel(ui_text(FIELD_LABELS[key])))
            editor = ModuleListEditor(key)
            editor.changed.connect(self._changed)
            self.modules[key] = editor
            column_layout.addWidget(editor)
            module_layout.addWidget(column)
        self.tabs.addTab(module_page,ui_text("Physics constructors"))
        cuts_page = QWidget()
        cuts_form = QFormLayout(cuts_page)
        self.cuts = {}
        for particle in ("gamma","e-","e+","proton"):
            control = QLineEdit()
            control.setObjectName("j2.cuts."+{"e-":"electron","e+":"positron"}.get(particle,particle))
            control.textChanged.connect(lambda value, particle=particle: self._top(particle,value,kind='cut'))
            self.cuts[particle] = control
            cuts_form.addRow(ui_text("Production cut")+" / "+particle,control)
        self.tabs.addTab(cuts_page,ui_text("Production cuts"))

    def bind_owner(self, owner):
        self._history_owner=owner
        for editor in (*self.row_editors.values(),*self.modules.values()):
            editor._history_owner=owner
        self.refresh_references()

    def refresh_references(self):
        for editor in self.row_editors.values():
            editor.refresh_reference()

    def _top(self,key,value,kind='top'):
        if self._projecting:
            return
        owner=getattr(self,'_history_owner',None)
        if owner is not None:
            owner.edit_sps(action={'kind':kind,'key':key,'value':value,'revision':owner._edit_session.revision})
        else:
            self._changed()

    def _changed(self,*args):
        if not self._projecting: self.changed.emit()

    def set_models(self,source,physics):
        self._projecting = True
        try:
            self.multiple_vertex.setChecked(source.multiple_vertex)
            self.phase_space_file.setText(source.phase_space_file)
            self.phase_space_recycle.setChecked(source.phase_space_recycle)
            self.row_editors["gps_sources"].set_rows(source.gps_sources)
            for key in ("regions","fields","bias_rules"):
                self.row_editors[key].set_rows(getattr(physics,key))
            for key,editor in self.modules.items(): editor.set_values(getattr(physics,key))
            for key,control in self.cuts.items(): control.setText(physics.particle_cuts.get(key,""))
        finally:
            self._projecting = False

    def collect_into(self,source,physics):
        owner=getattr(self,'_history_owner',None)
        if owner is not None:
            # Compatibility read adapter; no widget/row-list capture.
            snapshot=owner.run_path_snapshot()
            for target,model in ((source,snapshot.project.sourceEditor),(physics,snapshot.project.physicsEditor)):
                for field in fields(model):
                    setattr(target,field.name,deepcopy(getattr(model,field.name)))
            return
        # Model strings are the sole raw-draft storage. Capture even an invalid
        # programmatic setText before page.update_project; never replay a second
        # draft map over paths rebased during package relocation.
        for editor in self.row_editors.values(): editor.collect_current_row()
        source_values = {"gps_sources": deepcopy(self.row_editors["gps_sources"].rows),
                         "multiple_vertex": self.multiple_vertex.isChecked(),
                         "phase_space_file": self.phase_space_file.text(),
                         "phase_space_recycle": self.phase_space_recycle.isChecked()}
        physics_values = {}
        for key in ("regions","fields","bias_rules"):
            physics_values[key] = deepcopy(self.row_editors[key].rows)
        for key,editor in self.modules.items(): physics_values[key] = list(editor.values)
        physics_values["particle_cuts"] = {key:control.text() for key,control in self.cuts.items() if control.text()}
        for owner,values in ((source,source_values),(physics,physics_values)):
            if any(getattr(owner,key) != value for key,value in values.items()):
                for key,value in values.items(): setattr(owner,key,value)
                owner.is_dirty = True

    def interaction_controls(self) -> dict[str,QWidget]:
        """F5 event/merge ownership only; these are not redundant raw drafts."""
        result = {control.objectName():control for control in
                  (self.multiple_vertex,self.phase_space_file,self.phase_space_recycle)}
        for editor in self.row_editors.values():
            result[editor.list.objectName()] = editor.list
            result.update({control.objectName():control for key,control in editor.controls.items() if key != "editor_id"})
        for editor in self.modules.values():
            result[editor.list.objectName()] = editor.list
            result[editor.choice.objectName()] = editor.choice
        result.update({control.objectName():control for control in self.cuts.values()})
        result.update({button.objectName():button for button in self.findChildren(QPushButton) if button.objectName().startswith("j2.")})
        return result

    def editable_controls(self) -> dict[str,QWidget]:
        """Compatibility spelling of the interaction-only registration API."""
        return self.interaction_controls()

    def selection_state(self) -> dict[str,int]:
        result = {"j2.tabs":self.tabs.currentIndex()}
        result.update({f"j2.{key}.selection":editor.list.currentRow() for key,editor in self.row_editors.items()})
        result.update({f"j2.{key}.selection":editor.list.currentRow() for key,editor in self.modules.items()})
        return result

    def restore_selection(self,state: dict[str,int]) -> None:
        """Restore view hints after model projection; emit no changed/signals."""
        current = self.selection_state()
        if type(state) is not dict or any(key not in current or type(value) is not int for key,value in state.items()):
            raise ValueError(ui_text("Invalid J2 selection state"))
        lists = {f"j2.{key}.selection":editor.list for key,editor in {**self.row_editors,**self.modules}.items()}
        for key,value in state.items():
            if key == "j2.tabs":
                if not 0 <= value < self.tabs.count(): raise ValueError(ui_text("Invalid J2 tab selection"))
            elif not -1 <= value < lists[key].count(): raise ValueError(ui_text("Invalid J2 row selection"))
        previous = self._projecting
        self._projecting = True
        blockers = [QSignalBlocker(control) for control in self.interaction_controls().values()]
        blockers.append(QSignalBlocker(self.tabs))
        try:
            if "j2.tabs" in state: self.tabs.setCurrentIndex(state["j2.tabs"])
            for key,widget in lists.items():
                if key in state: widget.setCurrentRow(state[key])
            for editor in self.row_editors.values(): editor._select(editor.list.currentRow())
        finally:
            del blockers
            self._projecting = previous
