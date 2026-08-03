/**
 * 页面间共享的会话状态：当前作答、匹配结果、待对比选择。
 * 纯内存，不落盘、不上报。
 */
import { Answers, emptyAnswers, MatchResult, Scored } from './Types';

export class Session {
  private static answers: Answers = emptyAnswers();
  private static result: MatchResult | null = null;
  private static compareIds: string[] = [];

  static reset(): void {
    Session.answers = emptyAnswers();
    Session.result = null;
    Session.compareIds = [];
  }

  static getAnswers(): Answers {
    return Session.answers;
  }

  static setAnswers(a: Answers): void {
    Session.answers = a;
  }

  static setResult(r: MatchResult): void {
    Session.result = r;
  }

  static getResult(): MatchResult | null {
    return Session.result;
  }

  // ——— 对比选择（最多 3 个）———

  static compare(): string[] {
    return Session.compareIds;
  }

  static isPicked(id: string): boolean {
    return Session.compareIds.indexOf(id) >= 0;
  }

  static compareCount(): number {
    return Session.compareIds.length;
  }

  /** 返回 true 表示已加入；false 表示已达上限、未加入 */
  static addCompare(id: string): boolean {
    if (Session.isPicked(id)) {
      return true;
    }
    if (Session.compareIds.length >= 3) {
      return false;
    }
    Session.compareIds.push(id);
    return true;
  }

  static removeCompare(id: string): void {
    const i = Session.compareIds.indexOf(id);
    if (i >= 0) {
      Session.compareIds.splice(i, 1);
    }
  }

  /** 按结果排名顺序返回被选中的产品 */
  static pickedScored(): Scored[] {
    const r = Session.result;
    if (r === null) {
      return [];
    }
    return r.ranked.filter((s) => Session.isPicked(s.product.id));
  }
}
