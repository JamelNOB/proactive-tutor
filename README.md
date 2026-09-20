# ProActive-Tutor (名师微创导学决策引擎)

> **基于学生反馈的底层知识断裂精准逆向归因与最高效率动态微创教学决策系统**  
> 告别低效 AI 的长篇大论与废话灌输，复刻顶级高三补课名师的“微创认知手术”——**精准找准断点、20秒原子微切片、瞬间回弹主线、闭环防伪验证**。

---

## 🌟 核心设计哲学 (Core Philosophy)

普通 AI 在面对学生提问或做错时，通常会推倒重来，生成数千字的长篇大论，导致学生在认知过载中迷失主线。
**ProActive-Tutor** 践行名师带教的三铁律：
1. **差分逆向归因 (Differential Root-Cause Inversion)**：不看最终对错，只抓学生思维链与正确逻辑的**“第一个分叉断点”**，精准穿透表象语法，锁定底层缺失的前置公理或模型；
2. **最小充分干预决策树 (Minimum Intervention Cost, MIC)**：
   - **L0 聚光灯 (≤ 3s)**：仅圈出视线盲区，不给知识；
   - **L1 脚手架设问 (≤ 8s)**：单句提问激活既有记忆；
   - **L2 极限反例冲击 (≤ 10s)**：1 个反直觉极值击碎错误直觉；
   - **L3 原子微切片旁路 (≤ 20s)**：主线挂起，贷出单步纯算子，秒级回弹；
3. **极速回弹闭环 (Instant Snapback Loop)**：补丁打完的瞬间，像橡皮筋一样秒级弹回原题主线，让学生亲手推完卡住的那一步。

---

## 🏗️ 目录结构 (Repository Structure)

```
proactive-tutor/
├── core/
│   ├── __init__.py
│   ├── models.py         # 核心数据模型 (InterventionLevel, FaultType, AtomicOperator, StackFrame 等)
│   ├── engine.py         # 核心决策引擎 (PedagogicalCallStack, RootCauseTracer, PedagogicalDecisionEngine)
│   └── scenarios.py      # 黄金双场景库 (Softmax梯度反向传播 + CUDA 共享内存 Bank 冲突)
├── tests/
│   ├── __init__.py
│   └── test_engine.py    # 包含 L0~L3 分级干预、调用栈挂起回弹、超时熔断的完整单测套件
├── cli_tutor.py          # 极简高交互命令行终端 (支持实时键盘交互与 --simulate 演示)
└── README.md
```

---

## ⚡ 一键安装 (One-Click Installation for Antigravity & MCP)

任何人只要克隆本项目，运行 1 条命令，即可自动完成 **Antigravity Skill 注册 + MCP 服务端挂载 + 自检**：

```powershell
git clone https://github.com/JamelNOB/proactive-tutor.git
cd proactive-tutor
python install.py
```

> 💡 **在 Antigravity 中更省心**：直接在 Antigravity 聊天框发一句：  
> `“帮我安装这个技能：https://github.com/JamelNOB/proactive-tutor”`  
> AI 就会自动下载并运行 `install.py`，三秒完成配置！

### 支持其他 MCP 客户端（如 Claude Desktop / Cursor）
在你的 `claude_desktop_config.json` 或对应 MCP 配置文件中加入：
```json
{
  "mcpServers": {
    "proactive-tutor": {
      "command": "python",
      "args": ["<克隆路径>/proactive-tutor/mcp_server.py"]
    }
  }
}
```

---

## 🚀 快速上手 (Quick Start)

### 1. 运行自动化对抗单测
验证调用栈完整性、四级干预策略与超时熔断保护：
```powershell
pytest tests/test_engine.py -v
```

### 2. 运行自动化场景模拟对练
体验名师在学生卡壳时的秒级逆向归因与 20 秒原子切片回弹：
```powershell
# 场景一（期末突击）：Softmax Attention 梯度反向传播严密手推
python cli_tutor.py --simulate -s softmax

# 场景二（项目防穿帮）：CUDA 共享内存 32-way Bank Conflict 根因透视与错位优化
python cli_tutor.py --simulate -s cuda
```

### 3. 开启真实人机 1v1 交互终端
作为学生，亲自体验被名师带着推导与设套探坑：
```powershell
python cli_tutor.py -s 1   # 启动期末突击场景
python cli_tutor.py -s 2   # 启动项目防穿帮场景
```

---

## 📊 性能指标 (Performance Metrics)

- **单次决策推理耗时**：$< 0.05\text{ms}$（纯内存状态矩阵计算，零网络延迟）；
- **原子切片超时熔断**：默认 $\le 25\text{s}$，超时强制触发主线回弹，防止支线死锁；
- **话术字数约束**：L0 $\le 15$ 字，L1 $\le 30$ 字，L2 $\le 40$ 字，L3 $\le 60$ 字，彻底消灭 AI 废话。
