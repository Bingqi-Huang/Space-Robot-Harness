# 月面任务目录（Lunar Task Catalog）

## 1. 说明

本目录为 Acta Astronautica 论文的实验选型提供文献依据。论文在同一台仿真月面移动操作机器人
（LunarBot：四轮独立转向车 + RM-75 七自由度臂 + EG2 平行夹爪，无精细操作）上比较三种方法：
NASA PLEXIL 手写程序、EUROPA→PLEXIL 规划、以及我们的 LLM/VLM agent harness。Experiment I 需要
"covered"（基线预写方案已覆盖）与"held-out"（所需基础能力齐全，但任务级诊断/分解/能力组合未被
预先编写）两类任务情境。**用户要求：任务与情境选择必须首先匹配文献/机构规划中记载的真实未来月面
任务需求**，本目录是后续选型的候选池，一次性做透，此后不再重复调研。

调研范围覆盖：NASA Moon-to-Mars 架构文件（Architecture Definition Document、Civil Space
Shortfalls）、Lunar Surface Innovation Consortium (LSIC)、Artemis Base Camp / Fission Surface
Power (FSP) / Lunar Terrain Vehicle (LTV) / CLPS 相关文件、Lewis et al. 2022 (NTRS 20220013667)、
NASA 自主看护 (ISAAC) 项目、ESA (Argonaut、Moon Village CDF 研究)、CNSA/Roscosmos (ILRS)、JAXA
(LUPEX、Lunar Cruiser)、以及 ISS Dextre/SPDM、Robonaut、Restore-L/OSAM-1 等在轨维修/物流真实先例与
同行评审/会议文献（Acta Astronautica、i-SAIRAS、AIAA、IEEE Aerospace、arXiv 预印本等）。四路并行
调研均使用 WebSearch + WebFetch 实际检索、打开原文；仅见摘要/落地页的一律注明，无法打开正文的线索
不计入正式编号来源，也绝不编造。

调研日期：2026-09-17。任务/情境所需能力对照的"现有能力清单"引用自任务说明（导航、对接、手臂
READY/收纳、末端规划/移动、闭爪按压、抓取把手、导航中搬运负载、放置、松开、相机观测；计划中的
共享能力：VLM 语义场景问答）。

## 2. 来源清单

**NASA Moon-to-Mars 架构与需求文件**

1. Lewis, M.E., McCleskey, C.M., Alvarez, V.R., De Jesus Gomez Jr., J., Latorella, K.A., Gill, T.R.,
   Perotti, J.M., Zeitlin, N.P. "Uncrewed Lunar Surface Operations and Support Activities." NASA
   (KSC/LaRC), NTRS 20220013667（另有 AIAA 2022-4234 版本），2022-09-06。
   https://ntrs.nasa.gov/citations/20220013667 ｜ 类型：技术报告（会议论文）｜ 本人逐页读取全文
   28 页。本目录**最重要的单一来源**：明确写出机器人"caretaker"从物流仓库取备件、开舱、更换故障
   模块、验证的完整链条（§IV，p.7）；"Robotically performing some inspections, maintenance, or
   repair tasks on the power distribution equipment could reduce the surface crew workload"（p.15）；
   月尘导致设备（连接器、电机、密封件）性能下降、需要机器人除尘（§VIII.A，p.20）；故障管理/物流/
   通信延迟自主性等全面覆盖 Mission A、B 场景。
2. NASA. *Moon to Mars Architecture Definition Document*, Revision C, ESDMD-001, NASA/TP-20250010956,
   2025-12-12。https://www.lpi.usra.edu/lunar/strategies/resources/M2M_ACR2025_NASA-TP-20250010956_RevisionC.pdf
   ｜ 类型：机构架构规划文件 ｜ 由并行调研代理下载后用 pdftotext 读取全文相关章节。关键技术缺口：
   Gap 0501「Robotic Inspection, Maintenance, and Repair」（含"gaining access"作为缺口任务类型，
   p.223）、Gap 0801「Lunar Dust-Tolerant Systems and Dust Mitigation」（57 项缺口中优先级第 1，
   p.235）、Gap 0903「Power Management and Distribution between Surface Elements」（p.245，直接对应
   PDU 场景）、Gap 0701（命名"automated asset tracking"为所需子能力，p.233）、Gap 0808「Relocation
   of Large Assets on the Lunar Surface」（p.242）。
3. NASA. *2026 Civil Space Shortfalls*, 2026-01-12。
   https://www.nasa.gov/wp-content/uploads/2026/03/2026-civil-space-shortfalls.pdf ｜ 类型：机构需求
   缺口文件 ｜ 全文读取相关类别。类别 28「Autonomously monitor, inspect, maintain, and repair space
   assets」四条子项，直接对应 Mission A 的诊断-维护-验证链条；28.06 明确要求自主决策软件具备
   "explainable reasoning...necessary to establish trust"，呼应本文 harness 的可追溯性设计。
4. NASA. "Lunar Logistics Drivers and Needs" white paper, 2023 Moon to Mars Architecture Concept
   Review。https://www.nasa.gov/wp-content/uploads/2024/01/lunar-logistics-drivers-and-needs.pdf ｜
   类型：机构白皮书 ｜ 全文（3 页）读取。备件（spares）被列为独立物流类别，"As missions progress to
   longer durations, spares and maintenance items can become larger drivers of overall logistics
   mass"，支持 Mission B 的备件配送场景。
5. Tofil, T. "Overview of NASA's Fission Surface Power (FSP) Project." NASA GRC, NTRS 20220011870,
   2022-08-10。类型：机构技术报告（会议材料）｜ 全文读取。FSP 设计要求自主开关机循环，为 PDU 类
   电力基础设施的自主运行提供背景。
6. Kaldon, L. "Overview of NASA Fission Surface Power." NETS-2023, NTRS 20230006731。类型：机构技术
   报告 ｜ 全文读取。FSP 参考架构由反应堆舱、控制器舱、用户负载接口三个可分离单元经最长 1 km 电缆
   连接组成，为"电力分配单元"场景提供真实物理原型依据。
7. NASA. "NASA Pursues Lunar Terrain Vehicle Services for Artemis Missions," 2023-05-26。
   https://www.nasa.gov/news-release/nasa-pursues-lunar-terrain-vehicle-services-for-artemis-missions/
   ｜ 类型：机构新闻稿 ｜ 全文读取。"Engineers will be able to operate the LTV remotely to transport
   cargo and scientific payloads between crewed landing sites"，支持无人期间的地面间物流运输。
8. Deans, M., Badger, J., Smith, T. (NASA). "Integrated System for Autonomous and Adaptive Caretaking
   (ISAAC)." NTRS 20190029054, 2019-08-12。类型：机构技术报告 ｜ 全文（10 页）读取。三大能力支柱与
   本目录高度对应：Autonomous State Assessment（异常定位）、Autonomous Logistics Management（机器人
   货物搬运）、Integrated Fault Management（Detect→Locate→Patch 流水线）。
9. NASA STMD. "Autonomous Systems & Robotics" 页面。https://www.nasa.gov/autonomous-systems-robotics-2/
   ｜ 类型：机构网页 ｜ 全文读取。将 ISAAC 描述为"Remote and autonomous care taking of Gateway when
   crew are not onboard"，能力含"Maintenance, logistics management, utilization tasks, fault
   detection, isolation, and recovery"。
10. "Meet the Lunar Gateway's Robot Caretakers." *IEEE Spectrum*。https://spectrum.ieee.org/lunar-gateway-robots
    ｜ 类型：科技媒体报道（二手，但引用 NASA 在职人员原话）｜ 全文读取。引用 NASA 的 Julia Badger：
    出现故障时"we've got to have the ability to remotely or autonomously fix it"；Gateway 每年约 11
    个月无人值守。
11. Mikaelian, S.S. (NASA Armstrong). "Enabling Reliable, Fault-Tolerant Autonomous Lunar Habitats with
    High-Performance Spaceflight Computing." IEEE Aerospace Conference 2026, NTRS 20260000719。类型：
    同行评审会议论文 ｜ 读取前 6 页。给出"Fault Avoidance→Detection→Correction→Containment→
    Mitigation"标准流水线（Fig. 4），并指出"the inability to perform maintenance or replace parts on
    the Moon necessitates systems that can operate reliably for years without intervention"。
12. Fritz, A., Breeding, S., Tamasy, G. (NASA/LSIC). "NASA Dust Mitigation Technology Roadmap — LSIC
    Fall 2024." NTRS 20240013978。类型：机构技术路线图 ｜ 全文（8 页）读取。命名技术缺口"Shortfall
    1390: Power and Data Transfer in Dusty Environments"，能力类别"Dust Tolerant
    Components—connectors, bearings, seals, umbilicals"，直接支持 PDU/连接器被月尘影响的场景。
13. NASA. "Spacecraft Autonomous Inventory Tracking" 技术需求说明书。
    https://www.nasa.gov/wp-content/uploads/2024/09/8-inventory-tracking-spec-sheet-508.pdf ｜ 类型：
    机构技术需求文件 ｜ 全文读取。**直接证据**：ISS 上定位物资目前主要靠人工扫码和大量地面数据库
    支持，"Locating an item on ISS can take on the order of days without localization automation"；
    REALM-1 RFID 系统定位精度约 1.5–7.3 m，数据分析在地面完成需 4.8 小时——现实中"记录位置与实际
    位置不一致"的直接先例。
14. Gibb, M. (NASA JSC). "Inventory and Stowage Officer Lessons Learned." NRC 研讨会材料, 2011-04-27。
    https://sites.nationalacademies.org/cs/groups/depssite/documents/webpage/deps_063600.pdf ｜ 类型：
    机构内部报告（部分读取，第 1–14 页）｜ 含"nominal" 与"off-nominal cargo configuration"对比照片，
    真实记录了 ISS 存放位被超额占用/杂乱的情形。
15. NASA OIG. *NASA's Management of Spare Parts for its Flight Projects*, IG-18-001, 2017-10-05。
    **更正（2026-09-23）：此报告讲飞行项目备件管理，不是 ISS 存放位与记录不符，不可用于 B3/库存不符的依据。**
    https://oig.nasa.gov/docs/IG-18-001.pdf ｜ 类型：机构监察审计报告 ｜ 本人读取封面/目录/引言/
    Results in Brief。"Headquarters' Logistics Management Division's visibility into flight assets
    across the Agency and its ability to accurately account for flight inventory is limited and
    inconsistent."（Results in Brief）。

**国际机构计划**

16. CNSA & Roscosmos. *International Lunar Research Station (ILRS) Guide for Partnership*, V1.0,
    2021-08，提交至 UN COPUOS。
    https://www.unoosa.org/documents/pdf/copuos/2021/AM_3._China_ILRS_Guide_for_Partnership_V1.0Presented_by_Ms.Hui_JIANG.pdf
    ｜ 类型：机构间合作规划文件（英文官方版）｜ 全文（23 页）读取。三阶段路线图（勘察 2021–2025、
    建造 2026–2035、利用 2036 后）；五大设施中"Long-term Support Facility"与"Lunar Transportation
    and Operation Facility"直接对应基础设施维护与物流。"Lunar Transportation and Operation Facility
    will support various modules to move or hop on the lunar surface...for cargo transportation and
    operation for the long-term support system"；"ILRS-1 mission: Establishment of command center,
    basic energy and telecommunication facilities, to satisfy the needs of lunar infrastructure, lunar
    autonomous operations and long-term research."
17. CNSA/深空探测实验室 (DSEL). "International Lunar Research Station" 报告, 提交至 UN COPUOS,
    2023-05。https://www.unoosa.org/documents/pdf/copuos/2023/TPs/ILRS_presentation20230529_.pdf ｜
    类型：机构规划文件（部分读取，第 1–14/28 页）｜ 将 ILRS 定义为"a scalable and maintainable
    comprehensive scientific experiment facility"，长期自主运行、短期载人参与。
18. ESA-ESTEC Concurrent Design Facility. *Moon Village: Conceptual Design of a Lunar Habitat*,
    CDF-202(A), Issue 1.1, 2020-09（ESA UNCLASSIFIED – Releasable to the Public）。
    https://www.lpi.usra.edu/lunar/strategies/ESA-ESTEC_2020_MoonVillageLunarHabitatStudy.pdf ｜
    类型：机构技术研究报告（185 页）｜ 全文提取，重点章节精读。§4.3.4："occasional repairs and
    maintenance work...a 3D-printer could be used to manufacture tools and spare parts"；§7.1.4
    外部电力模块对接需要"a high power interface with a robotic connect/disconnect function"（与 PDU
    场景的机制高度相似）；§9.2.2.2 月尘覆盖使散热面/光学面吸收率上升、性能下降的"clean" vs
    "dusted"对比分析（跨机构印证月尘导致设备状态判读/性能改变的真实性）；报告自陈"Spare parts
    strategy has not been discussed at this stage...however impact on the mass budget can be
    extremely significant"——**备件策略本身被 ESA 列为尚未解决的真实缺口**，间接支持备件追踪/错放
    类情境的现实性。
19. Govindaraj, S., Sanz, I., But, A., et al.（Space Applications Services、DFKI、City University of
    London、LAAS-CNRS、PIAP-Space、GMV Aerospace、Thales Alenia Space 等，欧盟 Horizon 2020 PRO-ACT
    项目）. "Multi-Robot Cooperation for Lunar Base Assembly and Construction." i-SAIRAS 2020,
    paper 5073。https://www.hou.usra.edu/meetings/isairas2020fullpapers/pdf/5073.pdf ｜ 类型：同行
    评审会议论文 ｜ 全文（8 页）读取。异构机器人（轮式臂载车 Veles、六足 Mantis、移动龙门架）
    "cooperatively unload, transport large components and assemble an ISRU plant on the moon"，含
    标准化对接接口 HOTDOCK 与基于无线通信的故障恢复机制。该文是"多机协作/ISRU 建造"这一被本目录
    排除的候选任务族的具体真实先例（见第 3 节末）。
20. Redwire Corporation. "Redwire Awarded Contract by European Space Agency to Develop Robotic Arm
    Prototype for Argonaut Lunar Lander," 2024-05-22。
    https://ir.rdw.com/news-events/press-releases/detail/123/redwire-awarded-contract-by-european-space-agency-to
    ｜ 类型：企业新闻稿（报道真实 ESA 资助合同）｜ 全文读取。MANUS（"Manipulator for Argonaut
    Payload Needs and Unloading Support"）机械臂"will enable Argonaut's surface logistics operations
    such as offloading, precise positioning and retrieval of objects, and positioning of the
    lander"——真实资助中的月面货物搬运机械臂项目。
21. ESA. "Argonaut" 平台页。https://explorationscience.esa.int/platforms/argonaut/ ｜ 类型：机构网页
    ｜ 全文读取。"Europe's first multi-purpose logistics lander"，可运载至 1500 kg 货物，支持部署
    资产数月至数年；页面本身未涉及自主维护细节（如实说明，未过度引申，细节由 [20] 补充）。
22. GITAI. "GITAI Awarded JAXA Contract for Concept Study of Robotic Arm for Crewed Pressurized Lunar
    Rover," 2025-03-31。https://gitai.tech/2025/03/31/... ｜ 类型：企业新闻稿（报道真实 JAXA 合同）｜
    全文读取。机械臂任务含"unloading, handling, and installation of large payloads"及"remote and
    autonomous control operations during both uncrewed and crewed periods"。
23. JAXA. "Lunar Polar Exploration (LUPEX)" 任务页。https://humans-in-space.jaxa.jp/en/biz-lab/tech/lupex/
    ｜ 类型：机构网页 ｜ 全文读取。**如实说明**：内容聚焦科学勘测自主导航，未涉及维护/物流/故障
    场景，与本目录相关性弱，仅为完整披露检索结果而列出。

**在轨维修/物流真实先例与机构网页**

24. Canadian Space Agency. "Fueling up in Space: The Robotic Refueling Mission (RRM)."
    https://www.asc-csa.gc.ca/eng/iss/rrm/ ｜ 类型：机构网页 ｜ 全文读取。Dextre 执行剪线、揭隔热层、
    模拟加注等真实在轨维修操作，其中一项"only about a millimetre of clearance"，说明接近/操作精度
    要求真实存在。
25. NASA. "RRM Phase 1"（NExIS 项目页）。https://www.nasa.gov/nexis/rrm-phase-1 ｜ 类型：机构网页 ｜
    全文读取。列出 Dextre 完成的六项真实在轨维修任务（剪线帽、阀门操作、连接器盖移除等）。
26. JPL. "CADRE Mission Overview." https://robotics.jpl.nasa.gov/.../cadre-mission-overview/ ｜ 类型：
    机构网页 ｜ 全文读取。三台月面车经 mesh 网络自主协作，"making decisions without constant human
    intervention"，为通信/地面依赖降低的自主性提供真实工程先例（非维修任务本身）。
27. NASA Goddard SVS. "Restore-L: Robotic Satellite Servicing Project," 2016。
    https://svs.gsfc.nasa.gov/12023/ ｜ 类型：机构网页 ｜ 全文读取。7 自由度机械臂执行"rendezvous
    with, inspection, repair and refueling of a client satellite"。
28. eoPortal. "OSAM-1 (On-orbit Servicing, Assembly, and Manufacturing-1)."
    https://www.eoportal.org/ftp/satellite-missions/o/OSAM-1_040322/OSAM-1.html ｜ 类型：技术参考数据库
    （非同行评审，但资料翔实）｜ 全文读取。**诚实说明**：专门检索是否有"操作前先核实目标实际配置
    是否与预期一致"的记录，未能在本页确认——这是一个明确的文献空白，而非佐证。
29. JPL Robotics. "MER Surface Navigation." https://www-robotics.jpl.nasa.gov/.../surface-navigation/ ｜
    类型：机构技术网页 ｜ 全文读取。真实记录 Spirit 右前轮失效后拖行继续行驶、Opportunity 右前转向
    电机卡死在 ~7° 仍可继续行驶数年——能力退化后任务级适应的直接先例。
30. Ridgeway, B. "From Tools to Trash: Marshall's Payload Stowage Team Tracks It." NASA, 2017-02-24。
    https://www.nasa.gov/missions/station/from-tools-to-trash-marshalls-payload-stowage-team-tracks-it/
    ｜ 类型：机构网页文章 ｜ 全文读取。ISS 航天员常"丢失"已入库物资，"can take days or weeks to
    find"，直接支持存放位状态与记录不符的现实性。
31. Coleshill, E., Oshinowo, L., Rembala, R., et al. "Dextre: Improving maintenance operations on the
    International Space Station." *Acta Astronautica*, 64(9–10):869–874, 2009。
    https://www.sciencedirect.com/science/article/abs/pii/S0094576508003627 ｜ 类型：同行评审期刊论文
    ｜ **仅核实书目信息**（标题/作者/期刊/卷期页码经 ADS/ResearchGate/NTRS 多方比对一致），
    ScienceDirect 正文与摘要页均返回 403，未能读取摘要原文，不引用其中具体表述，仅确认该文真实
    存在且主题为 Dextre 执行 ORU 维修任务。

**VLM / 语义感知支持（面向 Experiment II）**

32. Foutter, M., Gammelli, D., Kruger, J., Foss, E., Bhoj, P., Guffanti, T., D'Amico, S., Pavone, M.
    "Space-LLaVA: A Vision-Language Model Adapted to Extraterrestrial Applications." arXiv:2408.05924,
    2024-08-12（2025-01-18 修订）。https://arxiv.org/abs/2408.05924 ｜ 类型：预印本 ｜ 本人复核
    摘要。**如实更正**：论文具体示例场景为火星（"identify a site of scientific interest on
    Mars"），并非月面；整体方法（VLM 语义推理用于地外场景理解）跨行星通用，仅作为 VLM 应用于地外
    机器人语义任务的方法论类比，不作为月面专属证据使用。
33. Carrasco, A., Nedungadi, M., Zucchelli, E.M., et al. "Visual Language Models as Operator Agents in
    the Space Domain." AIAA SciTech 2025 / arXiv:2501.07802。类型：会议论文预印本 ｜ 摘要页全文读取
    （正文 PDF 解析失败）。"VLMs can enhance autonomous control and decision-making in space
    missions"，含用相机机器人"inspect and diagnose physical space objects, such as satellites"的
    用例。
34. Romero-Azpitarte, S., Guerra, A., Alonso, M., et al. "CISRU: a robotics software suite to enable
    complex rover-rover and astronaut-rover interaction." ASTRA 2023 / arXiv:2311.03122。类型：会议
    论文预印本 ｜ **仅摘要页核实**（"a high level of autonomy is required, powered by AI and
    multi-agent autonomous planning systems"）；网络检索摘录中提到该系统的 LAMARR 用例可判断太阳能
    板损坏并生成向航天员的协作请求，但正文 PDF 未能打开核实，**该细节不作为已核实证据使用**，仅
    作为需要进一步核实的线索列出。

**无人看护先例、规划文献与 VLM 异常检测补充**（独立检索路径，本人逐条 WebFetch 复核）

35. NASA (Tavares, F.). "Meet ISAAC, Integrating Robots with the Space Stations of the Future."
    NASA.gov, 2021-08-11。https://www.nasa.gov/missions/station/meet-isaac-integrating-robots-with-the-space-stations-of-the-future/
    ｜ 类型：机构网页 ｜ 全文读取并复核。真实记录：ISS 生命支持系统探测到二氧化碳浓度过高后，
    Astrobee 机器人"Bumble"自主导航至指定通风口，"used computer vision to automatically detect the
    foreign object blocking the vent – an 'astronaut sock'"，随后"called for help to clear the
    blockage"（复核后更正表述：是站上生保系统而非 Bumble 本身探测到 CO2 异常，Bumble 负责定位/
    确认遮挡物）。**这是"遮挡物阻断关键功能→机器人自主诊断遮挡→请求/协作清除"这一情境结构（对应
    cover_obstruction）目前检索到的最具体真实先例**，且发生在无人看护流程中，而非抽象的维修活动
    列举。
36. Rabideau, G., Russino, J., Branch, A., Dhamani, N., Vaquero, T.S., Chien, S., de la Croix, J.-P.,
    Rossi, F. "Planning, Scheduling, and Execution on the Moon: the CADRE Technology Demonstration
    Mission." Proc. 24th Int'l Conf. on Autonomous Agents and Multiagent Systems (AAMAS 2025),
    2025-05-19，Detroit, MI（亦见 arXiv:2502.14803）。https://arxiv.org/abs/2502.14803 ｜ 类型：
    同行评审会议论文 ｜ 全文（HTML）读取并逐字复核关键引文。CADRE 是 2025/2026 执行中的真实 CLPS
    搭载三车协同月面任务；其规划执行系统 §3.2.4 原文（本人复核逐字一致）："because no additional
    tasks are created during planning, **the task network must contain all of the tasks we will ever
    need**"。**这是当前最先进的、已实际执行的月面在轨规划系统仍需穷举任务网络的一手证据**，直接
    支持本文"held-out 情境需要任务级分解未被预先编码"这一论点具有现实必要性，而非仅是本文的理论
    假设——建议在第 5 节或论文相关工作中引用，用于回应"为何不直接让 EUROPA/CADRE 式规划器处理
    held-out 情境"的审稿质疑。
37. Keenan, P.A.（Canadian Space Agency）, Read, D.A.（NASA JSC）. "Dexterous Operations on ISS and
    Future Applications." 2011-02-15，NTRS 20100036524。https://ntrs.nasa.gov/citations/20100036524
    ｜ 类型：机构技术报告 ｜ 本人 WebFetch 复核摘要（**摘要级**，未获取完整 PDF 正文）。描述
    Dextre/SPDM 执行 ORU"detailed inspection and the removal and replacement"以避免航天员出舱，
    并总结"lessons learned from the planning and execution of SPDM commissioning"，涉及地面遥操作
    的真实挑战——是 Mission B 备件更换任务结构（故障→移除→更换→验证）目前检索到的最贴近真实操作
    的先例，比现有 [24][25][31] 更聚焦于"lessons learned"这一维度。
38. JPL / Northrop Grumman. "AWIMR: Autonomous Walking Inspection and Maintenance Robot." JPL
    Robotics 项目页。https://www-robotics.jpl.nasa.gov/what-we-do/research-tasks/awimr-autonomous-walking-inspection-and-maintenance-robot/
    ｜ 类型：机构技术网页 ｜ 全文读取并复核。仿节肢动物机器人在桁架/板状结构上行走，自主或遥操作
    完成巡检与维护，明确目标"reducing requirements for humans to perform extra vehicular activities
    (EVAs)"。**如实说明**：该项目面向在轨（非月面）基础设施，仅作为"自主巡检维护机器人降低人类
    介入需求"这一动机的跨场景类比证据，不直接支持月面具体场景。
39. Kalaycioglu, S., De Ruiter, A., Misra, A.K., Yoshida, K. "Editorial: Innovative robotics for lunar
    exploration and on-orbit servicing." *Frontiers in Robotics and AI*, 2026。
    https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2026.1835560/full ｜
    类型：同行评审期刊（编者按）｜ 全文读取。"Robotic technologies are essential for performing a
    wide range of tasks including planetary surface exploration...infrastructure inspection, and
    on-orbit servicing"——作为综述性文献佐证巡检维护与在轨服务是当前机器人学界公认的月面/轨道机器
    人核心任务类别，支持 Mission A/B 的整体选题方向。
40. Wang, S., Kojouharov, V., Chung, L.Y., Morton, D., Cutkosky, M. "Long-Reach Robotic Cleaning for
    Lunar Solar Arrays." arXiv:2603.29240, 2026-03-31。https://arxiv.org/abs/2603.29240 ｜ 类型：
    预印本 ｜ 全文读取并复核。"over time lunar dust accumulates on these large solar arrays, which
    can rapidly degrade panel output and reduce mission lifetime"；提出长臂柔顺清洁机器人方案（约
    2 N 恒力擦拭）。**如实说明**：清洁动作本身属于本文明确排除的精细操作范畴，此文仅作为"月尘导致
    基础设施性能/可读性下降"这一物理机制的独立同行评审证据（与 [18] §9.2.2.2 跨机构印证），**不
    建议**将"清洁"设计为机器人能力——A4 情境中机器人只需变更观测策略确认真值，不执行除尘动作。
41. Ronecker, M.P., Foutter, M., Elhafsi, A., Gammelli, D., Barakaiev, K., Pavone, M., Watzenig, D.
    "Vision Foundation Model Embedding-Based Semantic Anomaly Detection." arXiv:2505.07998,
    2025-05-12。https://arxiv.org/html/2505.07998 ｜ 类型：预印本 ｜ 全文（HTML）读取。定义
    "semantic anomaly"为"contextually invalid combinations of familiar objects/states"，用视觉
    基础模型嵌入与正常场景库比对实现检测，属检测/定位方法，不含恢复策略。**如实说明**：验证场景
    为自动驾驶而非航天，仅作为 VLM 语义异常检测方法论的跨领域类比，支持 Experiment II 的 VLM 能力
    设计方向，不作为月面任务需求本身的证据。

## 3. 任务目录

以下"所需能力"对照任务说明给出的现有能力清单；标注【新】的为清单外能力（含是否属于精细操作的
判断）。

### Mission A — 基础设施巡检维护

**A1（已有）PDU 故障复位（covered）**
故障报告指出某 PDU 红灯亮、按钮无遮挡。文献依据：[1] p.7 caretaker 更换故障模块全流程、p.15
"robotically performing...power distribution equipment"、p.16 故障管理-维修-验证流水线；[2] Gap
0501/0903；[3] 类别 28.02；[8][9] ISAAC 故障管理支柱；[11] 电力分配+故障流水线；[6] FSP 参考架构
的可分离供电单元设计。建议类型：covered（三方法均预写此标准流程）。所需能力：navigate、dock、arm
READY、press with closed jaws、camera observation——均在现有清单内。语义观测需求：确认目标 PDU
灯色。可行性：无需改动场景（已实现）。

**A2（已有）cover_obstruction（held-out：access/obstruction）**
服务盖靠在故障 PDU 上遮挡按钮。文献依据：**[35] NASA ISAAC/Astrobee "Bumble" 真实案例——生保系统
探测异常后，机器人自主定位通风口、用视觉识别出遮挡物（一只袜子）并请求协作清除**，是本目录检索到
的与本情境结构最贴近的真实先例；[1] p.16 "gaining access to replace/repair the faulty asset" 被
明确列为维修活动步骤之一；[2] Gap 0501 将"gaining access"列为 IM&R 缺口任务类型，Gap 0808
「Relocation of Large Assets」；[18] §7.1.4 外部电力模块需"a robotic connect/disconnect
function"，佐证电力基础设施本就需要机器人完成接近/介入动作。建议类型：held-out——诊断"为何按不到
按钮"→决定先移开遮挡物，属任务级分解，未被预先编码。所需能力：navigate/dock、grasp a
handle（盖的把手）、carry a payload（放到一边或货架）、release、press——均在清单内。语义观测需求：
判断按钮是否被遮挡、遮挡物是否可移动。可行性：无需改动场景（已实现，`heldout_cover_obstruction`）。

**A3（已有）status_mismatch（held-out：状态与报告不一致）**
故障报告指向的 PDU 灯为绿色，实际红灯在另一台 PDU 上。文献依据：[2] Gap 1002「Autonomous
Monitoring」；[3] 类别 28.05"autonomously detect and diagnose off-nominal conditions"；[1] p.24
"presentation of these nuances is important to support diagnosis of discrepancies"。**如实说明**：
以上支持的是"自主诊断报告与实测不一致"这一能力类别的必要性，但未检索到"故障报告指错具体设备编号"
这一具体先例的文献记录——本情境为在已证实需求类别下的合理外推，而非文献中直接复现的真实事件，建议
论文中如实注明（另见 A4 的融合方案，可显著加强文献依据）。建议类型：held-out（需要"报告不可信、
需现场核验"这一未被预先编码的推理）。所需能力：navigate（逐台确认）、camera observation、【计划
中】VLM 语义场景查询（判断灯色）。可行性：无需改动场景（已实现，等待 Phase E 感知落地）。

**A4（新）dust_obscured_indicator（held-out：状态与报告不一致，且有更强、跨机构的文献依据）**
默认观测角度/距离下，PDU 状态灯因月尘覆盖而颜色难以判读，需要变换观测位或抵近才能确认真实状态。
文献依据：[2] Gap 0801「Lunar Dust-Tolerant Systems and Dust Mitigation」——57 项技术缺口中优先级
**第 1**；[12] "Shortfall 1390: Power and Data Transfer in Dusty Environments"，能力类别"Dust
Tolerant Components—connectors, bearings, seals"；[1] §VIII.A（p.20）"dust intrusion...must
consider dust intrusion during maintenance...dislodging and cleaning dust from equipment...could be
performed robotically"；**跨机构印证**：[18] ESA §9.2.2.2 通过"clean" vs "dusted"对比实验证实月尘
薄层会改变散热/光学表面的可读性能，与"月尘改变状态灯可读外观"机制一致（该证据来自散热片而非状态
灯，如实注明为机制类比而非同一部件）；**[40] Wang et al. 2026（arXiv）进一步独立佐证月尘会
"rapidly degrade panel output"，是电力类基础设施（与 PDU 同属供电系统）因月尘导致性能/可读性下降
的第三方同行评审证据**，但该文的清洁动作本身超出本文能力范围，不建议采纳。建议类型：held-out，且
比 A3 更贴合文献（用月尘代替"报告出错"作为不一致的物理成因，是二者的自然合并——见第 5 节推荐）。
所需能力：navigate to a alternate
view pose、camera observation、【计划中】VLM 语义场景查询。**明确排除**：擦除月尘属于精细操作
（拂拭/刷洗），不在机器人能力范围内——本情境只考验"换角度/换观测策略以确认真值"的推理，不新增
物理能力。可行性：小（灯罩材质加一层半透明积尘贴图/降低 VLM 置信度模拟，不改变几何与碰撞体）。

**A5（新）capability_substitution（held-out：能力/路径替代）**
标准接近位（前方）被占用或不可达（如维修车停在常规停靠位），必须换用另一侧接近角度或以另一条已
注册能力路径完成按压。文献依据：[1] §VIII.A（p.14 Surface Mobility 中"obstacle/collision
avoidance"作为标准功能）；一般性支持——**未检索到"PDU 常规接近位被占用"这一具体先例**，如实说明。
建议类型：held-out（要求在不新增能力的前提下选择替代路径/接近角）。所需能力：navigate to a
pose/feature（备用工位）、dock at a work pose、press with closed jaws——均在清单内，无新增。语义
观测需求：判断常规接近位是否可用。可行性：小（复用已有资产，仅新增一个可选停靠点）。

### Mission B — 物流与服务

**B1（已有）配送备用 ORU（covered）**
从 depot slot 0 取备用 ORU 送到指定 PDU 的备件架。文献依据：[1] p.7、p.19"robotic caretakers
capable of precision positioning, aligning, and manipulation of objects may be used to remove,
install, and stow supplies and equipment"；[2] p.40 AS&R 概述"asset handling...logistics
management"；[4] 备件为物流质量的主要驱动因素；[8] ISAAC"Autonomous Logistics
Management"（机器人货物搬运）；[19] PRO-ACT"cooperatively unload, transport large
components"；[20] ESA MANUS 机械臂"offloading, precise positioning and retrieval of objects"；[22]
JAXA/GITAI 机械臂负责"unloading, handling, and installation of large payloads"。建议类型：
covered；**[37] Keenan & Read (2011) 记录的 Dextre/SPDM 真实 ORU 更换操作（"detailed inspection
and the removal and replacement of On-orbit Replaceable Units"）是本任务"取件→运送→安装"结构最
贴近的历史真实先例**。所需能力：navigate、dock、grasp a handle、carry a payload under
navigation、place、release——均在清单内。可行性：无需改动（已实现）。

**B2（已有）destination_occupied（held-out：状态与预期不符）**
目标备件架被一个返回的货箱占用。文献依据：[14] NRC 材料中"nominal" vs "off-nominal cargo
configuration"真实照片对比，记录 ISS 存放位被超额占用；[2] Gap 0808 支持"先挪走占位物"这一分解。
**如实说明**：未检索到"备件架恰好被货箱占用"这一具体先例，上述证据支持的是存放位被意外占用这一
现象类别的普遍性。建议类型：held-out。所需能力：navigate/dock、grasp a handle、carry a payload、
place、release——均在清单内。语义观测需求：判断货架是否已被占用、占用物是否可移动。可行性：无需
改动场景（已实现）。

**B3（已有）spare_swapped（held-out：状态与manifest不符，证据最强）**
清单说 ORU 在 slot 0，实际在 slot 1。文献依据：[13] NASA REALM-1 技术需求说明书——ISS 上"Locating
an item...can take on the order of days without localization automation"，RFID 系统精度约
1.5–7.3 m 且地面处理耗时 4.8 小时，**是"记录位置与实际位置不一致"的直接现实先例**；[15] NASA OIG
IG-18-001："ability to accurately account for flight inventory is limited and inconsistent"；[2]
Gap 0701 命名"automated asset tracking"为所需子能力（暗示现状不足）；[18] ESA 自陈"Spare parts
strategy has not been discussed at this stage...however impact on the mass budget can be extremely
significant"——**连 ESA 的正式概念研究都承认备件追踪策略尚未成型**，进一步支持备件记录与实际不符
的现实可能性。建议类型：held-out——本目录中文献支持最扎实的情境之一。所需能力：navigate（逐槽核
实）、【计划中】VLM 语义场景查询（识别哪个物体是真正的 ORU）、grasp/carry/place——除 VLM 外均在
清单内。可行性：无需改动场景（已实现，等待 Phase E 感知落地）。

**B4（已有，A/B 共享）route_block（held-out：能力/路径替代）**
未建图的停放车辆挡住计划路线，需绕行。文献依据：[29] JPL MER 真实车轮/转向故障后继续行驶的先例
（能力退化后的路径级适应）；[1] p.14 "obstacle/collision avoidance" 作为月面车标准功能描述；[26]
CADRE"making decisions without constant human intervention"。**如实说明**：未检索到"另一台车辆
恰好停在规划路线上"这一具体先例，证据支持的是"动态/未建图障碍物需要自主绕行"这一能力类别的普遍性。
建议类型：held-out。所需能力：navigate（Nav2 已具备绕行能力）——在清单内，无新增。可行性：无需
改动（已实现）。

**B5（新）which_object_is_spare（held-out：语义识别，服务于 B3 的感知前提）**
备件架上有外观相似的多个物体，需要通过语义查询而非位置假设判断哪个是真正的 ORU。文献依据：[32]
Space-LLaVA、[33] Carrasco et al. VLM 用于"inspect and diagnose physical space objects"、[34]
CISRU（仅摘要级支持，"a high level of autonomy is required, powered by AI"）。建议类型：either——
可作为 B3 的感知子任务，也可独立作为 Experiment II 的新能力验证案例。所需能力：【计划中】VLM 语义
场景查询——不在现有清单内，需先注册。语义观测需求：区分外观相似物体的身份（非仅颜色/位置）。可行
性：无需改动场景（复用已有 ORU/crate 资产）。

**B6（新）misplaced_crate_relocate（held-out：状态与预期不符，B2 的变体）**
返回的货箱未按规程放回其"正确"归置位，而是随意放在别处，机器人需要先找到货箱再决定后续动作（不同
于 B2 直接假设占用即可见）。文献依据：[30] "From Tools to Trash"——ISS 航天员常"丢失"已入库物资，
"can take days or weeks to find"；[14] 存放杂乱的真实照片证据。建议类型：held-out。所需能力：
navigate、【计划中】VLM 语义场景查询（在多个候选位置中定位货箱）、grasp/carry/place——除 VLM 外
均在清单内。可行性：无需改动场景（复用已有 crate 资产，仅需允许其生成在非默认位置）。

**B7（新，Experiment II 候选）注册 VLM 语义场景问答能力**
不是一个任务情境，而是任务说明中"计划中共享能力"的正式落地：回答"哪个灯是红色/货架是否被占用/
哪个物体是备件"等语义问题。文献依据：[32][33][34]（VLM 用于空间语义诊断的必要性）；[41] Ronecker
et al. 2025 提出的"semantic anomaly"检测方法论（视觉基础模型嵌入 vs. 正常场景库，跨领域类比，非
航天专用）；[39] Frontiers 编者按将"infrastructure inspection"列为月面/轨道机器人公认核心任务；
[3] 类别 28.06"explainable reasoning...necessary to establish trust"（强调自主决策软件需可解释，
呼应本文 harness 设计）。建议类型：Experiment II 新能力（冻结后引入，测量达到可信支持所需的工程
量）。所需能力：本身即为待注册能力，明确**不在**现有清单内。可行性：无场景变更，属于能力注册/
工程投入问题。

### 其他候选任务族：不建议新增第三条任务族

调研中出现的强相关但机制不同的方向——ISRU/月壤处理与建造（[2] ISRU 功能描述、[19] PRO-ACT 项目
"cooperatively unload, transport large components and assemble an ISRU plant"这一**真实、同行
评审、已有硬件验证**的先例）、多机协作探测（[26] CADRE）——均因涉及重型设备/多机协调/精细装配，与
"无精细操作、单机器人"的范围约束不符而不建议纳入；[19] 恰好证明该方向确有真实文献支持，只是机制
（多机协作+大型构件装配）与本文单机具身不匹配，因此排除理由是"范围不符"而非"缺乏文献"。通信中断
（[1] p.5、[3] 类别 28.04、[11]、[19] 基于 RF 通信的故障恢复机制）是**跨任务条件**而非独立任务
族，更适合作为 Experiment II 的 harness/系统能力测试维度（见第 5 节），而非月面基地场景中的新
地点/新资产。

## 4. 现有情形评估

| 情形 | 文献支持 | 建议 | 理由 |
|---|---|---|---|
| Mission A covered（PDU 故障复位） | 强（[1][2][3][8][9][11]） | 保留 | 需求文件与真实项目（ISAAC）明确列出该能力链条，是最被充分证实的情境 |
| A held-out cover_obstruction | 强（[35] ISAAC/Astrobee 真实遮挡-诊断-求助先例、[1] p.16、[2] Gap 0501/0808、[18] §7.1.4） | 保留 | 有具体真实事件（非仅抽象需求条目）直接对应"遮挡物阻断关键功能→自主诊断→清除"的情境结构 |
| A held-out status_mismatch | 中（能力类别有支持：[2][3][1]p.24；**具体先例未检索到**） | 保留但如实标注 | 建议在论文中说明这是"自主诊断能力需求"的合理外推，并考虑第 5 节的月尘融合方案以加强证据 |
| Mission B covered（配送 ORU） | 强（[1][2][4][8][19][20][22]） | 保留 | 备件物流是文献反复强调的真实需求，且与 Lewis 2022 的 caretaker 范例、ESA MANUS 等真实资助项目直接对应 |
| B held-out destination_occupied | 中（[14] 真实照片证据，具体"货架被占用"先例未检索到） | 保留 | 现象类别（存放位意外占用）有真实文档支持，情境设计合理 |
| B held-out spare_swapped | 强（[13][15][2][18]，本目录证据最扎实的情境） | 保留 | REALM-1 说明书几乎是逐字对应的现实先例，且 ESA 自陈备件策略尚未成型进一步佐证 |
| held-out route_block | 中（[29][1]p.14[26]，具体"车辆挡路"先例未检索到） | 保留 | "未建图/动态障碍物需绕行"是行星车自主性的标准要求类别 |

**关于 held-out 情境有效性的额外文献支撑**：一个可能的质疑是"为何不直接让 EUROPA 式规划器/CADRE
式在轨规划系统处理这些 held-out 情境"。[36] Rabideau et al. 2025（CADRE，2025/2026 真实执行的
CLPS 月面任务，非本文假设）的规划执行系统论文明确写道，因为规划阶段不产生新任务，"the task
network must contain all of the tasks we will ever need"——即当前最先进、已实际飞行的月面在轨
规划系统本身仍要求任务网络穷举预置。这为本文"held-out 情境需要任务级分解未被预先编码"的实验设计
提供了独立于本文假设的一手证据，建议在论文相关工作或第 5 节引用。

## 5. 推荐组合

> **已被取代（2026-09-23）**：最终 held-out 选择见 `docs/heldout_design.md`（L0–L4 新奇阶梯）。以下保留为调研记录。

**Experiment I — Mission A：** covered = A1；held-out 三选二/三，覆盖不同类别——
access/obstruction 用 **A2 (cover_obstruction)**；状态与报告不一致建议用**融合版 A3+A4**：将
status_mismatch 的物理成因具体化为"月尘薄膜导致灯色误读"（灯本身状态正确但被尘土遮蔽，机器人默认
观测角度读出错误颜色，需换角度/抵近复核）——这样可同时获得 [2] Gap 0801（优先级第一）、[12]
Shortfall 1390、[1] §VIII.A、[18] §9.2.2.2 四重跨机构支持，比单纯"报告指错编号"更贴近文献且更
真实；能力/路径替代用 **A5 (capability_substitution)**。

**Experiment I — Mission B：** covered = B1；held-out 用 **B3 (spare_swapped，证据最强，优先保留)**、
**B2 (destination_occupied)**，能力/路径替代用共享的 **route_block (B4)**。

**Experiment II 候选（1–2 个）：**
1. **新能力：VLM 语义场景问答（B7）**——直接解决 A3/A4/B3/B5/B6 的感知前提，文献支持明确
   （[32][33][34][41]方法论、[39]任务类别定位），且是仓库自身 TODO（Phase E）中已知的下一步阻塞
   项，工程量可清晰度量（冻结后从"无此能力"到"通过 status_mismatch/spare_swapped 验证"）。
   **与计划冲突（主 agent 复核注）**：按 execution_plan，VLM 语义观测是实验一冻结前就要注册的共享
   能力，A3/A4/B3 等实验一 held-out 情形依赖它，因此不能再作为实验二的"新能力"。若实验二要做新能力
   注册，需另选一个实验一情形不依赖的能力。
2. **新任务情境：无人期间的自主巡检-诊断-取件-维修全链条**（类似 [1] p.7 的 caretaker 范例、
   [8] ISAAC 的 Detect→Locate→Patch 流水线、以及 [35] Astrobee/ISAAC 真实的"异常探测→定位遮挡→
   求助清除"闭环，把 Mission A 与 Mission B 串成一次连续无人任务，不等待地面逐步确认）——这是本
   目录中单一方向支持力度最高、且有具体真实事件（[35]）而非仅抽象需求条目的组合场景，适合作为
   "新增任务级知识"的 Experiment II 案例。

以上为建议，最终选择由用户决定。
