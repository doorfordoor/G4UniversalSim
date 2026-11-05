# H2 体积过滤与动能能谱最小示例

从本目录运行：

```powershell
C:\path\to\G4UniversalSim.exe --config main.ini --macro run.mac --output output
```

期望：`output/spectrum_fluence_t0.csv` 中 `bin = 5`（1.0 MeV，`[1.0, 1.1) MeV`）
的加权注量为 `1 mm^-2`，underflow/overflow 为 0；`run_summary.txt` 含
`spectrum_csv_schema_version = 1`、`status = completed`、完成事件 100。

配置字段、单位、边界与限制见 `docs/H2过滤计分与能谱.md`。
