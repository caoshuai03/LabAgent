<!--
 @author: caoshuai.cs
 @date: 2026-07-25 14:48
 @description: LabAgent RAG 评测报告
-->

# RAG 评测报告

本次共评测 100 条问题。

## 1. 总体结果

| 方法 | Recall@20 | ContextPrecision | ContextRecall | Faithfulness | ResponseRelevancy | AnswerCorrectness |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 100.0% | 80.7% | 100.0% | 89.0% | 82.2% | 70.0% |
| current_with_rerank | 99.0% | 73.4% | 96.7% | 88.6% | 78.6% | 69.5% |
| current_without_rerank | 100.0% | 83.6% | 100.0% | 89.9% | 83.9% | 66.9% |

## 2. RAGAS 状态

- baseline: 已完成
- current_with_rerank: 已完成
- current_without_rerank: 已完成

## 3. 逐题对比

| id | 问题 | baseline Recall@20 | current_with_rerank Recall@20 | current_without_rerank Recall@20 | baseline 来源 | current_with_rerank 来源 | current_without_rerank 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TRIAL_741_QUERY_3 | 阵内智则当年跟藤原纪香办那场婚礼，大概花了多少钱？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_284_QUERY_2 | 《西南忠魂》这部剧背后的制作人是谁来着？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_789_QUERY_2 | 达曼旁边那几个算卫星城的地方都有哪些？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_763_QUERY_0 | Bee Gees 那张 This Is Where I Came In 在原创专辑里排第几？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_713_QUERY_3 | 卡洛除了王室头衔外，还管着哪些骑士团的大团长职位？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_678_QUERY_1 | 路口镇现在下面大概管多少个村和社区？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_778_QUERY_4 | 牛津词典里对“暴发户”这个说法大意怎么讲？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_735_QUERY_2 | 钱谦益给李日华那本文集写序时，是怎么夸他的文章气质的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_20_QUERY_2 | 那须盐原站以前还没改名的时候叫什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_269_QUERY_3 | 牛车水后来没那么挤，主要是因为什么东西出现了？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_234_QUERY_3 | 夜来香这种植物一般在哪些地方能见到？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_455_QUERY_1 | 《伏尔泰的朋友们》大概是用什么写法来讲那几个人的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_426_QUERY_0 | AltiVec 让处理器处理数据更快后，实际会帮到哪些任务？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_142_QUERY_0 | 魏夫人魏玩的字叫什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_534_QUERY_0 | 元皇后原本是哪里人，祖籍算哪里？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_641_QUERY_0 | 芙蓉洞具体是在重庆武隆的什么位置？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_234_QUERY_2 | 夜来香结出来的种子长什么样，有什么明显特征？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_648_QUERY_3 | 爱普格评分在产科里通常拿来做什么记录或比较？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_554_QUERY_2 | EXILE 的《real world》为什么能第一次拿到 Oricon 单曲榜第一？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_235_QUERY_1 | 猴面包树为什么会被叫成“笨蛋水果”？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_607_QUERY_0 | 成公英原来是哪一路势力手下的将领？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_516_QUERY_0 | 六十进制这个计数传统最早是从哪里来的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_540_QUERY_1 | 佐敦谷南道为什么资料里又会写成佐顿谷南道、北道？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_142_QUERY_3 | 魏玩的词通常偏向写哪些题材？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_282_QUERY_1 | 地球体育场满座大概能坐多少观众？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_800_QUERY_2 | 那个游戏里玩家是靠什么把敌人泡住的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_482_QUERY_2 | 蒙泰罗在 2005 美国大奖赛最后排在第几？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_154_QUERY_3 | 尤金袋鼠这种袋鼠体重大概有多重？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_239_QUERY_4 | 龙胆一般长在多高海拔的地方？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_265_QUERY_2 | 放线菌酮是卡住蛋白质合成里的哪一步来影响转译的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_555_QUERY_1 | 长宗我部元亲治理领地时推行过什么制度？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_375_QUERY_0 | 弗里西亚群岛这个岛链大概是怎么形成的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_583_QUERY_1 | 乌尔巴克齿龙的模式种是谁命名的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_654_QUERY_1 | 亚太基金会算是哪种类型的研究机构？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_420_QUERY_0 | 西奥多·庞维勒最早那本诗集叫什么名字？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_549_QUERY_4 | 到 2015 年，这所学院高级职称教师有多少人？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_188_QUERY_4 | 黄鳍紫鱼最大体长大概能到多少？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_552_QUERY_1 | ROH 到底偏酸式还是碱式电离，主要看什么因素？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_81_QUERY_1 | 昌昌遗址里那十个城堡当时主要拿来干什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_563_QUERY_3 | 瓦士本市男女收入平均下来分别是多少？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_273_QUERY_1 | 杨朝祥什么时候拿到学士学位的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_137_QUERY_4 | 那个狮子印章在国家事务里具体是给谁用、用来盖什么的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_814_QUERY_1 | 洛拉·帕尼亚尼出生地是哪儿？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_569_QUERY_1 | 长宗我部家是在什么事件之后归到丰臣家下面的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_122_QUERY_0 | “台湾电视公司节目列表”这条目主要是在列什么内容？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_160_QUERY_2 | 冷湖那边是发现石油以后才开始建设的吗，时间是哪年？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_321_QUERY_4 | 泰森食品买希尔夏品牌一共花了多少钱，含债务的话怎么算？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_11_QUERY_4 | 1993 年 3 月长谷川町子那边发生过什么离奇事件？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_526_QUERY_2 | 高英叔侄为什么当时那么招人反感？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_791_QUERY_0 | 扁掌龙亚科的化石大概在哪些洲都发现过？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_956_QUERY_0 | 国足球年度最佳运动员这个奖是谁赞助的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_161_QUERY_0 | 耶利米相关的圣经著作有哪些？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_632_QUERY_1 | 这部漫画原作是谁创作的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_987_QUERY_0 | 内帕特纳赫谷那条运输线以前主要运的是什么东西？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_803_QUERY_1 | 潘嘉丽是哪国或哪里出身的人？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_648_QUERY_1 | Apgar 评分具体由哪几项组成？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_199_QUERY_0 | 五月艾到底是什么植物？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_309_QUERY_2 | 蒋巨峰在 1984 年中到 1985 年初那段时间担任什么职务？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_211_QUERY_3 | 克伦贝格尔是在哪个国家出生的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_126_QUERY_2 | 《宇宙奇兵》当年在台湾台视是什么时段播的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_839_QUERY_0 | 赛里木湖以前的古称叫什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_607_QUERY_2 | 韩遂后来为什么会考虑投靠羌人？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_641_QUERY_4 | 芙蓉洞那个石膏花支洞，是凭哪项东西号称世界第一？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_519_QUERY_0 | 怡良一开始是在清朝哪个衙门任职？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_326_QUERY_1 | 挪威海螯虾主要分布在哪一片海域？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_959_QUERY_0 | 鬼室福信最后是怎么死的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_193_QUERY_3 | 马来穿山甲体长大概多少厘米？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_221_QUERY_1 | 苏佩维埃尔是什么情况下开始写第一本寓言故事的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_277_QUERY_4 | 刘七最后的死法是什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_563_QUERY_2 | 瓦士本市现在主要靠什么产业？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_600_QUERY_0 | 南宁二中这个简称全称是什么学校？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_782_QUERY_2 | 那起事故里飞机最后冲出跑道防护堤时速度多快？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_654_QUERY_4 | 亚太基金会现任 CEO 还兼着哪些身份？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_979_QUERY_2 | 杨昊为什么后来去了贵州人和？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_155_QUERY_0 | 斯氏腔吻鳕主要分布在哪些海域？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_99_QUERY_1 | 《格斗天王》第一集播出时收视率多少？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_583_QUERY_0 | 乌尔巴克齿龙大概生活在白垩纪的哪个阶段？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_880_QUERY_3 | 香港凉茶铺卖的凉茶里不能掺什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_63_QUERY_0 | 吴双战在 1969 年 9 月到 1970 年 4 月那段做什么职务？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_111_QUERY_4 | 那些经纪商为什么会想协商制定公共管理条例？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_762_QUERY_4 | 叶盛茂二审那次，高院最后怎么判的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_184_QUERY_1 | 百老汇剧院这个统称为什么会叫百老汇？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_123_QUERY_4 | 兰比尔的 40 号球衣退役主要是在纪念什么贡献？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_341_QUERY_1 | 泰国国家和王室那个标志叫什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_778_QUERY_2 | 英文里“暴发户”这个词源头是哪种语言？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_870_QUERY_1 | 鸟类学者长峰真弓去调查后发现了什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_405_QUERY_2 | 黑龙江省博物馆那栋楼属于什么建筑风格？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_321_QUERY_2 | 莎莉公司在东南亚用的广告口号是什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_845_QUERY_1 | 魏舒在史书里通常被称作什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_718_QUERY_4 | 名车博览馆设在碧海蓝天的哪个位置？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_920_QUERY_0 | 牛佬主要是做什么职业的？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_690_QUERY_2 | 广州北回归线塔那里，什么时候站在塔底会没有影子？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_708_QUERY_2 | CS/MPQ-78 的射控追踪雷达距离精度是多少？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_519_QUERY_1 | 怡良当广东巡抚时，禁烟运动主要配合了哪两个人？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_155_QUERY_4 | 斯氏腔吻鳕平时主要吃什么？ | 100.0% | 0.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_898_QUERY_3 | 纽西兰鸡毛松对毛利人来说都能派上哪些用场？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_697_QUERY_1 | 小榄精神病治疗中心通常收治或收留哪类人？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_534_QUERY_1 | 元皇后后来是哪位皇帝的皇后？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_690_QUERY_1 | 广州北回归线标志塔塔身做成 23.5 米是在暗示什么？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |
| TRIAL_639_QUERY_4 | 天生三桥里青龙天坑和神鹰天坑大概有多深、多大？ | 100.0% | 100.0% | 100.0% | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md | cmrc2018_kb_markdown.md |

## 4. 失败/差异样例

### TRIAL_155_QUERY_4
- 问题：斯氏腔吻鳕平时主要吃什么？
- 标准答案：几乎是以多毛类为食，偶在胃中发现甲壳类
- 黄金证据：斯氏腔吻鳕为辐鳍鱼纲鳕形目鼠尾鳕科的其中一种。本鱼分布于南日本太平洋侧、中国南海、台湾、菲律宾、印尼、澳洲北部、巴布亚纽几内亚、所罗门群岛、密克罗尼西亚、马里亚纳群岛等海域。水深300至610公尺。本鱼头部腹面光滑无鳞，眼窝极大，口小，吻部较迟钝，吻端有一小型的三角形棘突。齿为锥状，6列排成宽齿带；胸鳍基底之上后方有一大而明显的圆形黑斑；体被栉鳞，鳞片上之小棘平行排列，大小约略一致。发光器中长，由肛门起向前延伸止于两腹鳍基底之间。体为浅棕色，腹部白色，小型个体胸部的黑色圆斑会于死亡后消失。体长可达32公分。生活在混浊的泥沙底质上，几乎是以多毛类为食，偶在胃中发现甲壳类，生殖季在2至4月。栖息在400公尺左右的个体较大型，躯干部份可食，捕获数量甚多。
- baseline 答案：根据参考资料中关于斯氏腔吻鳕的食性描述，其主要食物为**多毛类**（如环节动物门的多毛类蠕虫），偶尔在胃中发现**甲壳类**（如磷虾等）。这一信息直接来源于问题“斯氏腔吻鳕主要以什么为食？”的明确答案。其他资料未提供更多关于其食性的细节。
- current_with_rerank 答案：根据提供的参考资料，没有关于斯氏腔吻鳕（学名：**Macrourus stelleri**）日常饮食习惯的明确描述。资料中主要涉及其分布、外形、生活环境及生殖季节等信息，但未提及该物种的具体食性。因此，无法基于现有资料回答其主要食物来源。
- current_without_rerank 答案：根据参考资料中关于斯氏腔吻鳕的食性描述，其**主要以多毛类为食**，偶尔在胃中发现甲壳类。这一信息来源于TRIAL_155_QUERY_4的明确答案。其他资料未提供与斯氏腔吻鳕食性相关的补充信息。
