/**
 * 问卷常量。5 题，第 1 题多选，其余单选。
 * 文案使用主动语态，说明点选后会发生什么，不使用夸大或带噱头的措辞。
 */
import { SceneKey, Scale, DeployNeed, RegionNeed, Level } from './Types';

export interface QOption {
  label: string;
  hint?: string;
  // 各题的取值类型不同，统一用字符串承载，读取时按题解析
  value: string;
}

export interface Question {
  key: 'scenes' | 'scale' | 'deploy' | 'region' | 'budget';
  title: string;
  hint: string;
  multi: boolean;
  options: QOption[];
}

export const QUESTIONS: Question[] = [
  {
    key: 'scenes',
    title: '你们主要想解决哪些场景的问题？',
    hint: '可多选。选得越具体，收敛得越准；不选则按覆盖面打分。',
    multi: true,
    options: [
      { label: '协作办公', value: 'collab', hint: '沟通、文档、审批' },
      { label: '客户与销售', value: 'crm', hint: '商机、客户、订单' },
      { label: '人力人事', value: 'hr', hint: '招聘、考勤、算薪' },
      { label: '财务费控', value: 'fin', hint: '账务、报销、预算' },
      { label: '项目研发', value: 'dev', hint: '需求、迭代、代码' },
      { label: '客服营销', value: 'svc', hint: '在线客服、工单' },
      { label: '数据分析', value: 'bi', hint: '看板、指标、分析' },
      { label: '合同签署', value: 'sign', hint: '电子合同、存证' }
    ]
  },
  {
    key: 'scale',
    title: '团队现在大概多少人？',
    hint: '按当前实际人数选，用于判断产品是否撑得住你的体量。',
    multi: false,
    options: [
      { label: '20 人以下', value: '1' },
      { label: '20–100 人', value: '2' },
      { label: '100–500 人', value: '3' },
      { label: '500 人以上', value: '4' }
    ]
  },
  {
    key: 'deploy',
    title: '对部署方式有要求吗？',
    hint: '选“需要私有化”会直接排除只提供云端的产品。',
    multi: false,
    options: [
      { label: '需要私有化部署', value: 'private', hint: '数据部署在自有环境' },
      { label: '云端 SaaS 就好', value: 'saas', hint: '开通即用，无需自建' },
      { label: '都行', value: 'any' }
    ]
  },
  {
    key: 'region',
    title: '数据合规上有什么要求？',
    hint: '选“纯国内业务”会排除数据主要在境外的产品。',
    multi: false,
    options: [
      { label: '纯国内业务', value: 'cn', hint: '数据须留在境内' },
      { label: '有海外业务', value: 'overseas', hint: '需要跨境或全球可用' },
      { label: '暂无明确要求', value: 'none' }
    ]
  },
  {
    key: 'budget',
    title: '预算大概到哪一档？',
    hint: '仅用档位匹配，不涉及具体报价。产品档位不超过你的预算会更靠前。',
    multi: false,
    options: [
      { label: '免费起步', value: '1', hint: '优先免费或低成本' },
      { label: '入门投入', value: '2' },
      { label: '中等投入', value: '3' },
      { label: '重投入', value: '4', hint: '预算充足' }
    ]
  }
];
