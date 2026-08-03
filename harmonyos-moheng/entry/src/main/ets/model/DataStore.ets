/**
 * 产品数据加载。数据来自 resources/rawfile/products.json，随包发布，全程无网络请求。
 * 加载一次后缓存于内存。
 */
import util from '@ohos.util';
import common from '@ohos.app.ability.common';
import { Product, ProductFile, SceneKey } from './Types';
import { SCENE_ORDER } from './Meta';

export class DataStore {
  private static products: Product[] = [];
  private static dataDate: string = '';
  private static loaded: boolean = false;

  /** 同步读取 rawfile 并解析。冷启动时调用一次即可。 */
  static load(context: common.UIAbilityContext): void {
    if (DataStore.loaded) {
      return;
    }
    const bytes: Uint8Array = context.resourceManager.getRawFileContentSync('products.json');
    const decoder = util.TextDecoder.create('utf-8');
    const text: string = decoder.decodeToString(bytes);
    const file: ProductFile = JSON.parse(text) as ProductFile;
    DataStore.products = file.products;
    DataStore.dataDate = file.updatedAt;
    DataStore.loaded = true;
  }

  static all(): Product[] {
    return DataStore.products;
  }

  static count(): number {
    return DataStore.products.length;
  }

  /** 数据整理时间，用于在 UI 展示新鲜度 */
  static updatedAt(): string {
    return DataStore.dataDate;
  }

  /** 数据集中实际出现过的场景数量（动态计算，不写死） */
  static sceneCount(): number {
    const seen: Set<SceneKey> = new Set();
    for (const p of DataStore.products) {
      for (const s of p.scenes) {
        seen.add(s);
      }
    }
    return seen.size;
  }

  /** 参与筛选的维度数：场景 / 规模 / 部署 / 合规 / 预算 = 5 */
  static dimensionCount(): number {
    return 5;
  }
}

export { SCENE_ORDER };
