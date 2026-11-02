"""Real offscreen Qt contract for the standalone L1 panel; no provider/backend call."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'gui'))
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QAccessible, QFont, QFontDatabase, QRawFont
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout
from g4usim_gui.core.i18n import ZH_CN, set_application_language, ui_text
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.widgets.config_agent_panel import (
    ACTIONS, AUTO_APPLY_TEXT, ConfigAgentPanel, EVALUATION_NOTE, LEVELS, PERMISSIONS,
)


def pump(app):
    app.processEvents()
    QTest.qWait(25)
    app.processEvents()


def test_new_task_authorization(panel, app):
    submit = QSignalSpy(panel.submitRequested)
    actions = QSignalSpy(panel.actionRequested)
    assert panel.max_calls.value() == 16 and panel.max_events.value() == 100
    assert panel.timeout.value() == 300
    assert panel.max_calls.maximum() == 32 and panel.max_events.maximum() == 100000
    assert panel.timeout.maximum() == 3600
    assert not panel.submit_button.isEnabled()
    assert all(not b.isEnabled() for b in panel.action_buttons.values())
    panel._submit()
    assert submit.count() == 0
    panel.prompt_edit.setPlainText('Set beamA energy to 1 GeV; review the detector first.')
    panel.prompt_edit.setFocus()
    pump(app)
    QTest.keyClick(panel.prompt_edit, Qt.Key_Return, Qt.ControlModifier)
    pump(app)
    assert submit.count() == 1
    payload = submit.at(0)[0]
    assert set(payload) == {'prompt', 'authorization', 'auto_apply', 'auto_run', 'evaluation_scope'}
    assert payload['authorization'] == {'allowed_actions': ['plan'], 'max_calls': 16, 'max_events': 100, 'timeout_seconds': 300}
    assert payload['auto_apply'] is False and payload['auto_run'] is False
    assert payload['evaluation_scope'] == 'input_run_completion'
    assert not panel.prompt_edit.toPlainText().endswith('\n')
    QTest.keyClick(panel.prompt_edit, Qt.Key_Tab)
    pump(app)
    assert not panel.prompt_edit.hasFocus(), 'Tab must leave the prompt, not insert a tab'

    # New-task form edits never grant an existing task any additional action.
    panel.allow_apply.setChecked(True)
    panel.allow_run.setChecked(True)
    panel.auto_apply.setChecked(True)
    panel.auto_run.setChecked(True)
    assert not panel.action_buttons['apply'].isEnabled()
    panel._request_action('apply')
    assert actions.count() == 0
    panel.submit_button.click()
    second = submit.at(1)[0]
    assert second['authorization']['allowed_actions'] == ['plan', 'apply', 'run']
    assert second['auto_apply'] is True and second['auto_run'] is True
    assert 'write_scope' not in second and 'scope' not in second
    assert 'source.particle' in panel.auto_apply.toolTip()
    assert panel.auto_apply.text() == ui_text(AUTO_APPLY_TEXT)

    panel.set_state({'status': 'awaiting_approval', 'allowed_actions': ['apply']})
    panel.allow_apply.setChecked(False)
    assert panel.action_buttons['apply'].isEnabled(), 'new form must not change active-task authorization'
    panel.action_buttons['apply'].click()
    assert actions.count() == 1 and actions.at(0)[0] == 'apply'
    panel.set_state({'authorization': second['authorization'], 'status': 'interrupted'})
    assert all(not b.isEnabled() for b in panel.action_buttons.values()), 'disk/journal authorization is not live permission'
    assert not panel.allow_apply.isChecked(), 'set_state must never restore authorization controls'


def test_busy_and_intents(panel):
    spy = QSignalSpy(panel.actionRequested)
    panel.set_state({'allowed_actions': list(ACTIONS)})
    for token, button in panel.action_buttons.items():
        button.click()
        assert spy.at(spy.count()-1)[0] == token
    assert spy.count() == len(ACTIONS)
    panel.set_busy(True)
    assert panel.action_buttons['cancel'].isEnabled()
    assert all(not b.isEnabled() for k,b in panel.action_buttons.items() if k != 'cancel')
    before = spy.count()
    panel._request_action('run')
    panel.action_buttons['cancel'].click()
    assert spy.count() == before+1 and spy.at(before)[0] == 'cancel'
    assert not panel.submit_button.isEnabled() and not panel.provider_fields.isEnabled()
    panel.set_state({'allowed_actions': ['apply']})
    assert not panel.action_buttons['cancel'].isEnabled()
    panel.set_busy(False)
    assert panel.action_buttons['apply'].isEnabled()
    assert not panel.action_buttons['run'].isEnabled()
    panel.set_state({'allowed_actions': 'apply'})
    assert not panel.action_buttons['apply'].isEnabled()


def test_credential_transfer(panel, app):
    panel.set_busy(False)
    panel.provider_toggle.setChecked(True)
    pump(app)
    assert panel.credential_id_edit.text() == 'l1-default'
    assert panel.auth_mode_edit.currentData() == 'none'
    assert not panel.credential_edit.isEnabled()
    assert panel.credential_edit.echoMode() == QLineEdit.Password
    transfers = []
    panel.providerChanged.connect(lambda data: transfers.append((deepcopy(data), panel.credential_edit.text())))
    for mode in ('session','system'):
        panel.auth_mode_edit.setCurrentIndex(panel.auth_mode_edit.findData(mode))
        panel.url_edit.setText('https://example.invalid/v1')
        panel.model_edit.setText('explicit-model-id')
        panel.credential_edit.setText('ephemeral-test-value')
        panel.provider_apply_button.click()
        data, observed_field = transfers[-1]
        assert set(data) == {'provider','url','model','auth_mode','credential_id','credential'}
        assert data['auth_mode'] == mode and data['credential_id'] == 'l1-default'
        assert data['credential'] == 'ephemeral-test-value' and observed_field == ''
        assert panel.credential_edit.text() == ''
        assert 'ephemeral-test-value' not in json.dumps(panel._state)
    panel.credential_edit.setText('another-test-value')
    panel.auth_mode_edit.setCurrentIndex(panel.auth_mode_edit.findData('none'))
    assert panel.credential_edit.text() == '' and not panel.credential_edit.isEnabled()
    panel.provider_apply_button.click()
    assert transfers[-1][0]['credential'] == '' and transfers[-1][0]['auth_mode'] == 'none'
    panel.set_state({'credential':'must-not-display','connection':{'provider':'local', 'url':'http://127.0.0.1:9999', 'model':'local-model', 'auth_mode':'system', 'credential_id':'reference-only', 'credential':'must-not-display'}})
    assert panel.provider_edit.currentData() == 'local'
    assert panel.auth_mode_edit.currentData() == 'system'
    assert panel.credential_id_edit.text() == 'reference-only'
    assert panel.credential_edit.text() == ''
    assert 'must-not-display' not in json.dumps(panel._state)
    panel.credential_edit.setText('clear-on-collapse')
    panel.provider_toggle.setChecked(False)
    assert panel.credential_edit.text() == ''
    panel.provider_toggle.setChecked(True)
    panel.credential_edit.setText('clear-on-busy')
    panel.set_busy(True)
    assert panel.credential_edit.text() == ''
    panel.set_busy(False)
    panel.credential_edit.setText('clear-on-hide')
    panel.hide()
    assert panel.credential_edit.text() == ''
    panel.show()
    panel.provider_toggle.setChecked(False)
    pump(app)


def sample_state():
    return {'task_id':'task-1','status':'awaiting_approval','goal':'Set beamA energy to 1 GeV',
            'summary':'The model says every test passed; this is not K1 evidence.',
            'allowed_actions':['apply','cancel'],
            'diff':[{'domain':'source','target':'beamA','field':'energy','before':'1 MeV','after':'1 GeV','reason':'explicit user goal'}],
            'questions':[{'id':'target','question':'Which sensitive volume is the detector?'}],
            'budget':{'max_calls':16,'calls_used':1,'max_events':100,'events_used':0,'timeout_seconds':300,'elapsed_seconds':2},
            'steps':[{'step':1,'action':'plan','status':'passed','record_id':'plan-record','run_id':'','detail':'plan only; no process'}],
            'evidence':{'fields':{'status':'passed','record_id':'k1-field-record','detail':'fields checked'},
                        'initialization':{'status':'stale','record_id':'old-init-record'},
                        'execution':{'status':'cancelled','record_id':'cancelled-run-record'}},
            'confirmation':{'message':'Review the proposed source change.','export_path':'bundle-not-created'}}


def test_projection_and_language(panel, app):
    state=sample_state();original=deepcopy(state)
    panel.set_state(state)
    assert state==original
    assert panel.diff_table.item(0,4).text()=='1 GeV'
    state['diff'][0]['after']='mutated externally'
    assert panel.diff_table.item(0,4).text()=='1 GeV'
    assert panel.evidence_table.rowCount()==4
    assert panel.evidence_table.item(3,1).text()==ui_text('Unobserved')
    assert panel.evidence_table.item(0,2).text()=='k1-field-record'
    assert panel.evidence_table.item(1,1).text()==ui_text('Stale')
    assert panel.evidence_table.item(2,1).text()==ui_text('Cancelled')
    panel.response_edit.setPlainText('Use the upstream sensitive target.')
    for language in ('zh_CN','en','zh_CN','en'):
        set_application_language(app,language)
        panel.retranslate_ui()
        assert panel.title_label.text()==ui_text('Configuration Agent')
        assert panel.accessibleName()==ui_text('Configuration Agent')
        assert panel.accessibleDescription()==ui_text(EVALUATION_NOTE)
        assert panel.evaluation_note.text()==ui_text(EVALUATION_NOTE)
        assert panel.clarification_response()=='Use the upstream sensitive target.'
        assert panel.evidence_table.item(3,1).text()==ui_text('Unobserved')
        for label in panel.findChildren(QLabel):
            if label.buddy() is not None:
                assert label.buddy().accessibleName()==label.text()
        assert panel.auth_mode_edit.itemText(2)==ui_text('System credential store')
    panel.set_state(original)
    assert panel.clarification_response()=='Use the upstream sensitive target.'
    panel.set_state({'questions':[{'id':'direction','question':'What beam direction?'}]})
    assert panel.clarification_response()==''
    assert panel.diff_table.rowCount()==panel.steps_table.rowCount()==0
    assert 'k1-field-record' not in panel.summary_view.toPlainText()
    assert all(panel.evidence_table.item(i,1).text()==ui_text('Unobserved') for i in range(4))
    panel.set_state({'status':{'invalid':'token'},'evidence':{'physics':{'status':['passed']}}})
    assert panel.status_label.text()==ui_text('Unobserved')
    assert panel.evidence_table.item(3,1).text()==ui_text('Unobserved')
    assert '0 /' not in panel.summary_view.toPlainText(), 'missing usage must not be fabricated as zero'
    spy=QSignalSpy(panel.actionRequested)
    panel.set_state({'allowed_actions':['cancel']})
    panel.retranslate_ui();panel.retranslate_ui()
    panel.action_buttons['cancel'].click()
    assert spy.count()==1, 'retranslation must not reconnect actions'


def test_accessible_layout(panel, app, output):
    observations=[]
    panel.set_state(sample_state())
    panel.prompt_edit.setPlainText('Long goal '+('beamA.energy; '*50))
    panel.provider_toggle.setChecked(True)
    for width in (760,400):
        panel.resize(width,640)
        for theme in ('light','dark'):
            apply_theme(app,theme)
            for language in ('en','zh_CN'):
                set_application_language(app,language)
                panel.retranslate_ui()
                panel.show()
                panel.activateWindow()
                # The earlier credential hide test deliberately deactivates the
                # offscreen top-level; give this test's own Qt window activation.
                QApplication.setActiveWindow(panel)
                pump(app)
                assert panel.width()==width and panel.height()==640, (width, panel.size(), panel.minimumSize(), panel.minimumSizeHint())
                for button in [panel.submit_button,*panel.action_buttons.values()]:
                    rect=QRect(button.mapTo(panel,QPoint()),button.size())
                    assert panel.rect().contains(rect),(width,language,button.text(),rect)
                    assert button.accessibleName()
                assert panel.content_scroll.height()>100
                assert panel.rect().contains(QRect(panel.evaluation_note.mapTo(panel,QPoint()),panel.evaluation_note.size()))
                # Actual Qt label relation, not only widget property.
                field=panel.max_events
                interface=QAccessible.queryAccessibleInterface(field)
                assert interface is not None
                label=next(x for x in panel.findChildren(QLabel) if x.buddy() is field)
                relations=interface.relations(QAccessible.Label)
                assert any(target.object() is label for target,role in relations)
                # Natural Tab traverses scroll descendants and reaches the fixed action bar.
                panel.prompt_edit.setFocus()
                pump(app)
                assert QApplication.focusWidget() is not None, (
                    'focus precondition', panel.isVisible(), panel.isActiveWindow(),
                    panel.prompt_edit.isVisible(), panel.prompt_edit.isEnabled(), panel._busy,
                    type(QApplication.activeWindow()).__name__, panel.prompt_edit.focusPolicy())
                seen=set()
                focus_trace=[]
                for _ in range(60):
                    focus=QApplication.focusWidget()
                    if focus is None:break
                    seen.add(focus)
                    focus_trace.append((type(focus).__name__, focus.objectName(), focus.accessibleName()))
                    if focus is panel.action_buttons['cancel']:break
                    QTest.keyClick(focus,Qt.Key_Tab)
                    pump(app)
                assert panel.submit_button in seen and panel.action_buttons['cancel'] in seen, (width, language, focus_trace[-18:])
                observed={'width':width,'height':640,'theme':theme,'language':language,'DPR':panel.devicePixelRatioF(),'footer_columns':panel._columns,'focus_cancel':panel.action_buttons['cancel'].hasFocus()}
                observations.append(observed)
                if output and width==760:
                    assert panel.grab().save(str(output/f'panel-{theme}-{language}.png'))
    before=(panel.content_scroll.horizontalScrollBar().value(),panel.content_scroll.verticalScrollBar().value())
    foreign=QDialog();layout=QVBoxLayout(foreign);other=QLineEdit();layout.addWidget(other)
    foreign.show();foreign.activateWindow();QApplication.setActiveWindow(foreign);other.setFocus();pump(app)
    assert QApplication.focusWidget() is other
    assert before==(panel.content_scroll.horizontalScrollBar().value(),panel.content_scroll.verticalScrollBar().value())
    foreign.close();foreign.deleteLater();pump(app)
    if output:(output/'observations.json').write_text(json.dumps(observations,indent=2)+'\n',encoding='utf-8')


def test_source_boundary(panel):
    source=ROOT/'gui/g4usim_gui/widgets/config_agent_panel.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(x and ('agent.' in x or 'project' in x or 'runner' in x) for x in imports)
    forbidden={'QProcess','QSettings','Popen','open','write_text','write_bytes','put','startDetached'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
            assert name not in forbidden,name
    for message in (EVALUATION_NOTE,AUTO_APPLY_TEXT,*ACTIONS.values(),*PERMISSIONS.values()):
        assert message in ZH_CN,message
    messages={s for _,s in panel._labels}|{s for _,s in panel._names}|{s for _,s in panel._tab_sources}
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('ui_text','ui_format'):
            if n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):messages.add(n.args[0].value)
    for table in (panel.diff_table,panel.steps_table,panel.evidence_table):
        messages.update(table.horizontalHeaderItem(i).text() for i in range(table.columnCount()))
    for message in messages:
        assert message in ZH_CN,message


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.output:args.output.mkdir(parents=True,exist_ok=False)
    app=QApplication.instance() or QApplication([])
    if os.name=='nt':
        for name in ('segoeui.ttf','msyh.ttc'):
            font_id=QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
            assert font_id>=0,name
        assert QRawFont.fromFont(QFont('Microsoft YaHei UI')).supportsCharacter(ord('配'))
    app.setStyle('Fusion');set_application_language(app,'en');apply_theme(app,'light')
    panel=ConfigAgentPanel();panel.resize(760,640);panel.show();pump(app)
    try:
        print('L1 panel DPR:',panel.devicePixelRatioF(),'Qt platform:',app.platformName())
        test_source_boundary(panel)
        test_new_task_authorization(panel,app)
        test_busy_and_intents(panel)
        test_credential_transfer(panel,app)
        test_projection_and_language(panel,app)
        test_accessible_layout(panel,app,args.output)
    finally:
        panel.close();panel.deleteLater();app.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
    print('L1 panel signals/authorization/ephemeral credential/evidence/i18n/layout PASS; no provider or backend execution')


if __name__=='__main__':main()
