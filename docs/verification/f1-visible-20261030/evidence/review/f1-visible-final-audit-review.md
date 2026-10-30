# F1 最终可见证据与关闭链独立审计

结论：**APPROVE，所列 F1 可见观察与正常关闭证据链完整，无阻断项。** 本审计核对原字节、字段与关联；视觉结论依据 root 的14次原生工具直接图像观察，本审计者没有看图，不冒称独立视觉复验。阶段正式关闭、文档及集成仍由主任务决定。

## 原字节与身份

证据根为 out/verification/f1-visible-20261030。observations.json包含14个不同label；每份原JPEG SHA均匹配记录，JPEG解码格式/1502×991等记录尺寸校验通过，每份对应非空UIA txt存在并另外计算SHA。窗口ID统一593824，标题带GUI ede037f26db6；图像未转换或重编码。详见本审计evidence.json逐图记录。

准备脚本针对最终host-state运行成功；代码import前、load时、exit时均为GUI checkout ede037f26db63f606e3ca086d5d586f222f428df。相对产品build f176d0ed4cea60b7ca5a80ed81017c9404ec1257仅文档改动，源码指纹db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc及测试指纹57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35一致；当前exe SHA实际重算f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8。host_sha256为bc0bce9a3b7e7479662315a2d29c023db998e3338c425c660ccb3183c9a50158。

host原字段observation_acceptance=pending保留，它是host初始状态而非本次人工观察结论。real_output_records.build_commit_matches_expected_head=false同样保留，正确反映文档HEAD不同于产品build；source_matches_loaded_code=true，不能把前一字段改写true来制造HEAD相等。

## 覆盖与边界

|观察|依据root原图观察记录的验收内容|
|---|---|
|01–04|运行与字节状态分开；build/input/output逐维只读详情；原始JSON默认折叠、点击展开；历史读取字节不等于当前源复核；process/run/thread及metadata自引用排除可辨|
|05–08|failed+verified并存；completed+不一致明确expected/observed且清表；legacy无内容哈希警告；缺登记文件不可用且不当零|
|09–11|合成历史的运行结果未证实与身份verified/missing分别呈现；仅现有splitter原生拖动扩宽详情，不外推J1自由布局|
|12–14|真实auto→ROOT及选择原因、产品build f176与GUI文档HEAD ede分别显示；3条历史读入记录；20登记输出、2run及worker0/1归属|

07-synthetic-legacy.jpg的视觉结论由root直接看图确认旧格式；同次07 UIA文本SHA与06完全相同，证明该文本滞后，不能用它佐证07。root另行读取文本的说明作为补充陈述，未伪造一个未保存的独立文本原件。长SHA在当前列宽下省略、横向滚动的观察不等于所有完整字节在一张截图直接可见；本次不新增“实际复制完整SHA成功”的未测结论。

09–11没有真实进程退出收据，故合成历史未覆盖可信success/failed运行结论；仅验证“结果未证实”与字节身份独立。合成failed+verified仅用于状态展示，不是新的真实失败运行物理验证。

另对out/verification/f1-visible-gdml调用统一output_evidence(...,fresh=True)重新做SHA：verified，manifest 4284260a76299214b50d846fc9340efac16835175a6fb70c7bed7e8db5eb4f65，20项登记输出。其真实后端fixture记录2workers、2run各2/2、3条输入、auto/root；字节验证和可见观察不证明物理结果正确。

## 原生关闭链

host-state PID38052、ready=true、closed=true；首次观察在load后、closed前。host-state原SHA 295556e20e5bf4d4c76fc4e0939e6869b173a889df30f233d2e9f5a1bbdf9a0c与process-receipt完全一致。process-receipt记录旧host会话40467退出0、最终host会话85274退出0，关闭方式为原生sky Alt+F4及进程轮询。post-close-windows.json是关闭后新list_windows收据，windows=[]。closed时间先于process收据。以上形成窗口观察→host关闭→进程退出→无剩余F1窗口链，不借测试控制file代替用户关闭。

本审计没有重跑产品、启动host、操作桌面或改任何原证据。旧自动归档原字节/pending措辞不追改；本次应作为单独可见补验归档，不能反写旧报告。process-receipt.phase_complete=false为采集当时事实，亦保留原字节。

## 新增独占审计产物

- f1-visible-final-audit-host.json：准备脚本对实际host-state的身份校验，保留visual_pending的机器边界。
- f1-visible-final-audit-evidence.json：14图/14UIA字节摘要、JPEG尺寸、关键收据SHA与关闭链核对。
- 本报告：人工整合root视觉观察与独立证据核对的有限approve；不把上述机器pending字段改成passed。
