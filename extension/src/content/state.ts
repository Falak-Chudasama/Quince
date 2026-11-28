export interface ElementDescriptor {
  role: string;
  name: string;
  tag: string;
  type?: string;
  inViewport?: boolean;
}

export interface Capture {
  url: string;
  title: string;
  scroll: number;
  maxScroll: number;
  viewportHeight: number;
  focusRef?: string;
  focusRole?: string;
  focusValue?: string;
  els: Map<string, ElementSnapshotItem>;
  messages: string[];
  modalRef?: string;
}

export interface ElementSnapshotItem {
  role: string;
  name: string;
  value?: string;
  checked?: boolean;
  disabled?: boolean;
  expanded?: string;
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
  public pendingPre: Capture | null = null;
  public pendingActionMeta: { method: string; ref?: string; targetRole?: string; startTime: number } | null = null;
  public unsubmittedEdit: { ref: string; url: string } | null = null;

  resetRefs(): void {
    this.generation++;
    this.nextRef = 1;
    this.refToEl.clear();
    this.descriptors.clear();
    this.pendingPre = null;
    this.pendingActionMeta = null;
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
