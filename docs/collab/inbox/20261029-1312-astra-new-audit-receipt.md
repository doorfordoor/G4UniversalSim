# Q1 新增审查来信登记

- 接收基线：隔离分支 `roadmap/2c-effective-config` / `3701990`，源码修复基线仍为 `f9930aa`。
- 来源：`D:\Geant4\G4UniversalSim\docs\collab\reviews\20261029-1254-astra-5465dbd-source-physics-field-review.md`；原审查基线 `5465dbd`。原报告与原始验证目录均留在 DSH 工作区，未搬移或改写。
- 涉及文件：`src/Field/FieldSetup.cc:99`、`src/Field/FieldConfig.cc:236`、`src/Config/IniReader.cc:195`、`src/Physics/PhysicsFactory.cc:492`。
- R-08：原审查以单/双 worker 反例确认嵌套局部场继承受 section 名称排序影响，列 P1。当前分支 Field/Physics 代码相对该基线无变更；纳入 Q1 优先复核与修复队列。这里只核对报告及代码差异，尚未重跑当前二进制，不把外部复现写成本对话新实测。
- V-02：max_step 默认的带电/中性粒子适用范围需明确。保持为适用范围与文档风险，不擅自改成内核缺陷，也不静默改变默认过程注册。
- 待对方动作：保留原始输入/日志/输出；无需因这份收件登记重跑或修改报告。原报告中的 R-01/R-02“未修复”仅描述 `5465dbd`，本分支已由 `f9930aa` 修复；两个分支状态不得混写。
- 当前计划仍以隔离 worktree 的 [ROADMAP](../../ROADMAP.md) 为准。Q1 同时承担接收增量审计和补齐覆盖，不依赖隔壁先审完。
