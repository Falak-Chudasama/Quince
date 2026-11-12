export interface ElementDescriptor {
  role: string;
  name: string;
  tag: string;
  type?: string;
  inViewport?: boolean;
}

export class ContentState {
  public frameId: number = 0;
  public frameKey: string = 'top';
  public generation: number = 0;
  public nextRef: number = 1;
  public refToEl = new Map<string, WeakRef<Element>>();
  public elToRef = new WeakMap<Element, string>();
  public descriptors = new Map<string, ElementDescriptor>();
  public indicatorOn: boolean = false;
  public lastCapture: any = null;

  resetRefs(): void {
    this.generation++;
    this.nextRef = 1;
    this.refToEl.clear();
    this.descriptors.clear();
  }

  getOrCreateRef(el: Element): string {
    const existing = this.elToRef.get(el);
    if (existing) {
      return existing;
    }
    const ref = this.frameKey === 'top' ? `e${this.nextRef++}` : `${this.frameKey}.e${this.nextRef++}`;
    this.elToRef.set(el, ref);
    this.refToEl.set(ref, new WeakRef(el));
    return ref;
  }

  getElement(ref: string): Element | null {
    const weak = this.refToEl.get(ref);
    if (!weak) return null;
    return weak.deref() || null;
  }
}

export const contentState = new ContentState();
