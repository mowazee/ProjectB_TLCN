import { lazy, type ComponentType, type LazyExoticComponent } from "react";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- ràng buộc giống React.lazy
type AnyComponent = ComponentType<any>;

/** React.lazy cho named export, giữ đúng kiểu props: lazyNamed(() => import("./X"), "X"). Mỗi feature P2 tách chunk. */
export function lazyNamed<M, K extends keyof M>(
  loader: () => Promise<M>,
  name: K,
): LazyExoticComponent<M[K] & AnyComponent> {
  return lazy(async () => ({ default: (await loader())[name] as M[K] & AnyComponent }));
}
