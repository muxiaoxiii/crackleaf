## v0.2.0 (2025-08-01)

### Feat

- **重构了界面,梳理了功能,基本可用**: 更新重构

## v0.1.0 (2025-08-01)

### Feat

- **1.-✅-真正支持拖拽导入（基于-tkinterDnD2）；-2.-✅-文件状态采用统一的数据结构管理（含-path、密码、icon、状态）；-3.-✅-单个文件可点击图标进行解锁；-4.-✅-“开始解锁”按钮加入图标并在处理时显示进度；-5.-✅-解锁失败信息写入日志文件-~/crackleaf_unlock_errors.log。**: Improvements

## v0.0.1 (2025-08-01)

### Feat

- initial GUI with unlock support, batch and per-file handling

### Features

- **ui**: 初始版本 GUI 完成，使用 Tkinter 构建固定窗口布局
- **import**: 支持通过点击和拖拽导入多个 PDF 文件
- **security**: 导入时自动检测 PDF 限制类型（加密/编辑受限）
- **unlock**: 支持单个 PDF 解锁，支持批量解锁，自动输出到系统 Downloads 文件夹
- **password**: 加密文档支持弹出密码输入框，解锁失败会提示
- **icon**: 文件列表中集成状态图标（🔒/🔓/❌）指示解锁状态
- **drag-out**: 支持从界面中拖出已解锁文件（路径复制至剪贴板）

### Improvements

- 使用 PyPDF2 检测限制类型和解密支持
- 解锁文件命名格式为 `_unlocked.pdf`，保持原文件不变

### Known Issues

- 拖拽导入功能仅模拟点击（需扩展为原生 drag-and-drop）
- 拖出文件为路径复制，未实现原生拖放
