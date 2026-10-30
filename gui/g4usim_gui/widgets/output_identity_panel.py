"""Read-only F1 identity presentation; parsing and verification stay in provenance."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTabWidget, QPushButton, QPlainTextEdit, QApplication
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.output.provenance import output_evidence


class IdentityTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setRootIsDecorated(False)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
    def copy_selection(self):
        rows = self.selectedItems()
        QApplication.clipboard().setText('\n'.join('\t'.join(row.text(i) for i in range(self.columnCount())) for row in rows))
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)


class OutputIdentityPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.run_label=QLabel();self.state_label=QLabel();self.note=QLabel()
        for label in (self.run_label,self.state_label,self.note):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setWordWrap(True)
        self.tabs=QTabWidget()
        self.build=IdentityTree();self.inputs=IdentityTree();self.outputs=IdentityTree()
        for tree in (self.build,self.inputs,self.outputs):
            self.tabs.addTab(tree,'')
        self.copy_button=QPushButton();self.copy_button.clicked.connect(self._copy)
        self.raw_button=QPushButton();self.raw_button.setCheckable(True)
        self.raw=QPlainTextEdit();self.raw.setReadOnly(True);self.raw.hide();self.raw.setMaximumHeight(160)
        self.raw_button.toggled.connect(self.raw.setVisible)
        buttons=QHBoxLayout();buttons.addWidget(self.copy_button);buttons.addWidget(self.raw_button);buttons.addStretch()
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        for item in (self.run_label,self.state_label,self.note,self.tabs):layout.addWidget(item)
        layout.addLayout(buttons);layout.addWidget(self.raw)
        self.run_title='Recorded run state'
        self._evidence=None;self._run='unknown';self._error=''
        self.refresh_language();self.clear()
    def _copy(self):
        self.tabs.currentWidget().copy_selection()
    def refresh_language(self):
        self.tabs.setTabText(0,ui_text('Program build identity'))
        self.tabs.setTabText(1,ui_text('Historical input reads'))
        self.tabs.setTabText(2,ui_text('Output file identity'))
        for tree,headers in ((self.build,['Identity field','Recorded value','Verification status']),
            (self.inputs,['Read sequence','Input kind / role','Recorded path','SHA-256 / bytes','Observation status']),
            (self.outputs,['Current relative path','Scope / run / thread','SHA-256 / bytes','Verification status'])):
            tree.setColumnCount(len(headers));tree.setHeaderLabels([ui_text(x) for x in headers])
        self.copy_button.setText(ui_text('Copy selected rows'));self.raw_button.setText(ui_text('Raw identity JSON'))
        if self._evidence is not None:self.set_evidence(self._evidence,self._run)
        else:self.clear(self._run,self._error)
    def clear(self,run_status='unknown',error=''):
        self._evidence=None;self._run=run_status;self._error=error
        for tree in (self.build,self.inputs,self.outputs):tree.clear()
        self.raw.clear()
        self.run_label.setText(ui_text(self.run_title)+': '+ui_text(run_status))
        state='Bytes differ from recorded hashes' if 'bytes mismatch' in error else 'Identity evidence unavailable'
        self.state_label.setText(ui_text('Output byte identity')+': '+ui_text(state))
        self.note.setText(error or ui_text('Select output evidence to inspect.'))
    def load_directory(self,directory,run_status='unknown'):
        self.clear(run_status)
        try:self.set_evidence(output_evidence(directory),run_status)
        except (ValueError,OSError) as error:self.clear(run_status,str(error))
    @staticmethod
    def _row(tree,values):
        row=QTreeWidgetItem([str(x) for x in values])
        for i,value in enumerate(values):row.setToolTip(i,str(value))
        tree.addTopLevelItem(row)
    def set_evidence(self,evidence,run_status='unknown'):
        self.clear(run_status);self._evidence=evidence
        document=evidence.document or {};p=document.get('provenance')
        self.state_label.setText(ui_text('Output byte identity')+': '+ui_text('Verified against recorded hashes' if p is not None else 'Legacy: content hashes unavailable'))
        self.note.setText(ui_text('Input rows describe historical bytes read, not current source verification or semantic acceptance.')+' '+ui_text('Hash consistency does not establish authenticated origin or physical correctness.')+' '+ui_text('Metadata excludes its own hash to avoid a circular self-reference. Unregistered extra files are outside this evidence set.'))
        self.raw.setPlainText(json.dumps({'provenance':p,'generated_files':document.get('generated_files',[])},ensure_ascii=False,indent=2))
        if p is None:
            self._row(self.build,['schema',document.get('schema','legacy'),ui_text('Legacy: content hashes unavailable')])
            for path in evidence.files:self._row(self.outputs,[str(path.relative_to(evidence.root)),'—','—',ui_text('Legacy: content hashes unavailable')])
            return
        self._row(self.build,['execution_id',p['execution_id'],ui_text('Recorded identity')])
        for key,value in p['build'].items():self._row(self.build,[key,value,ui_text('Unknown') if value=='unknown' else ui_text('Recorded identity')])
        self._row(self.build,['input_coverage',p['input_coverage'],p['input_observation']])
        for item in p['input_exclusions']:self._row(self.build,[ui_text('Excluded input IO'),item,ui_text('Not observed')])
        for row in p['inputs']:
            self._row(self.inputs,[row['sequence'],row['kind']+' / '+row['role']+' / '+row['capture_method'],row['path'],(row['sha256'] or 'null')+' / '+('null' if row['size_bytes'] is None else str(row['size_bytes'])),ui_text('Historical bytes read') if row['status']=='recorded' else ui_text('Not observed')+': '+row['reason']])
        for path,row in zip(evidence.files,evidence.records):
            status=ui_text('Metadata self hash excluded') if row['integrity_status']=='self_reference_excluded' else ui_text('Verified against recorded hashes')
            self._row(self.outputs,[str(path.relative_to(evidence.root)),row['scope']+' / '+('null' if row['run_id'] is None else str(row['run_id']))+' / '+('null' if row['thread_id'] is None else str(row['thread_id'])),(row['sha256'] or 'null')+' / '+('null' if row['size_bytes'] is None else str(row['size_bytes'])),status])
        self.outputs.setToolTip(ui_text('Metadata excludes its own hash to avoid a circular self-reference. Unregistered extra files are outside this evidence set.'))
        for tree in (self.build,self.inputs,self.outputs):
            for col in range(tree.columnCount()):tree.setColumnWidth(col,240 if col else 210)
