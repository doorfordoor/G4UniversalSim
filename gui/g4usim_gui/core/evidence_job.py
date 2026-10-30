"""Bounded, cancellable file verification with GUI-thread result publication."""
from concurrent.futures import ThreadPoolExecutor
import threading
from PySide6.QtCore import QObject, Signal
from g4usim_gui.output.identity import cancelled
from g4usim_gui.output.provenance import evidence_operation, evidence_key, output_evidence

_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='g4usim-evidence')


def verify_roots(roots):
    results={}
    with evidence_operation():
        for root in roots:
            if not root:continue
            try:results[evidence_key(root)]=output_evidence(root)
            except (ValueError,OSError) as error:results[evidence_key(root)]=error
    return results


class EvidenceJob(QObject):
    delivered=Signal(int,object,object)
    def __init__(self,owner):
        super().__init__(owner)
        self.pending=False;self._serial=0;self._event=threading.Event();self._closed=False;self._done=None
        self.delivered.connect(self._publish)
        owner.destroyed.connect(self.close)
    def cancel(self):
        self._serial+=1;self._event.set();self.pending=False
    def close(self,*args):
        self._closed=True;self.cancel();self._done=None
    def submit(self,work,done):
        self.cancel()
        if self._closed:return
        self.pending=True;self._done=done;serial=self._serial;event=threading.Event();self._event=event
        def run():
            token=cancelled.set(event.is_set)
            try:
                if event.is_set():return None
                return work()
            finally:cancelled.reset(token)
        future=_pool.submit(run)
        def completed(future):
            try:result,error=future.result(),None
            except Exception as exc:result,error=None,exc
            if event.is_set():return
            try:self.delivered.emit(serial,result,error)
            except RuntimeError:pass  # Owner was destroyed; never publish to it.
        future.add_done_callback(completed)
    def _publish(self,serial,result,error):
        if self._closed or serial!=self._serial:return
        self.pending=False
        callback=self._done;self._done=None
        if callback:callback(result,error)


def close_evidence_jobs(root):
    """Only call after the owner has decided to accept its close event."""
    for job in root.findChildren(EvidenceJob):
        job.close()
