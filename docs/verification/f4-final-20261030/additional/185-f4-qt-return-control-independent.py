import sys,json,gc,argparse
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QWidget
parser=argparse.ArgumentParser();parser.add_argument('mode');args=parser.parse_args()
app=QApplication([]);widget=QWidget()
if args.mode=='property_none':
    def action():widget.setProperty('probe',None)
elif args.mode=='property_bool':
    def action():widget.setProperty('probe',True)
elif args.mode=='void_update':
    def action():widget.update()
elif args.mode=='object_name':
    def action():widget.setObjectName('probe')
elif args.mode=='style_polish':
    def action():widget.style().polish(widget)
elif args.mode=='dynamic_names':
    def action():widget.dynamicPropertyNames()
else:raise ValueError(args.mode)
for _ in range(10):action()
gc.collect();before=sys.getrefcount(None)
for _ in range(100):action()
after=sys.getrefcount(None)
print(json.dumps({'mode':args.mode,'iterations':100,'before':before,'after':after,'delta':after-before}),flush=True)
widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
