# AGENT.md

请你永远优先阅读 @AGENT/research_content.md，理解整个 repo 的目标是完成这个学术 research 任务。永远以完成科学研究和获得研究结果为导向。接着选择性的阅读 @AGENT/execution_plan.md。这是我们整个 project 提前准备的计划。如果没有发现实际 code 和实验结果与该文档不符合的时候，请你坚持计划。

1. 较大的开发任务开 branch 或者 worktree（放在仓库内 .worktree/<name>）；小改动（几行修复、配置、文档、infra 小修）直接在 main 上提交，不要为了小任务开分支，没必要太复杂。开发合并以后删除过时的 worktree 和 branch，并及时清理 debug，pilot，smoke 测试产物。
2. 开发过程中及时更新 todo.md 和 handoff.md, 而且应该是覆盖式更新。两个文档不能超过 150 行。不要把所有内容都记录在内。
3. 减少 pytest，非必要不测试。
4. 严禁 hash 校验，严禁做防御性 coding，严禁为了 research 过程中极少出现的 corner case 做防御。