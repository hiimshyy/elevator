import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode
} from "react";

// =============================================================================
// Live-Region Announcer — Elevator PDM Operations Console
// Requirements: 6.6, 6.7
//
// A single app-level provider renders two persistent visually-hidden nodes
// near the root so any view can push loading (polite) or error (assertive)
// messages without managing its own live region. Views call
// `announcePolite` / `announceAssertive` when a Data_State transitions to
// loading or error; AT picks up the DOM mutation within the 1-second budget
// defined by Requirements 6.6 and 6.7.
// =============================================================================

export interface Announcer {
  /** Announce loading or other status text politely (Requirement 6.7). */
  announcePolite: (message: string) => void;
  /** Announce an error or other urgent message assertively (Requirement 6.6). */
  announceAssertive: (message: string) => void;
}

const LiveRegionContext = createContext<Announcer | null>(null);

/**
 * Visually-hidden style applied to both live-region nodes. The classic
 * "sr-only" recipe keeps the elements in the accessibility tree while
 * removing them from the visual layout. Both the deprecated `clip` and the
 * modern `clipPath` are set so older and newer assistive technologies are
 * covered.
 */
const SR_ONLY_STYLE: CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  clipPath: "inset(50%)",
  whiteSpace: "nowrap",
  border: 0
};

interface LiveRegionProviderProps {
  children: ReactNode;
}

/**
 * Provider that renders two persistent ARIA live regions (one polite, one
 * assertive) and exposes the announce functions through context. Mount this
 * once near the root of the application (see task 20.1).
 */
export function LiveRegionProvider({ children }: LiveRegionProviderProps): JSX.Element {
  const [politeMessage, setPoliteMessage] = useState("");
  const [assertiveMessage, setAssertiveMessage] = useState("");

  // Timer handles so a follow-up announcement supersedes any pending one.
  const politeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const assertiveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (politeTimerRef.current !== null) {
        clearTimeout(politeTimerRef.current);
        politeTimerRef.current = null;
      }
      if (assertiveTimerRef.current !== null) {
        clearTimeout(assertiveTimerRef.current);
        assertiveTimerRef.current = null;
      }
    };
  }, []);

  /**
   * Push a message into one of the live regions. The region is first cleared
   * and then the new text is written on the next tick so that repeating the
   * same message still produces a DOM mutation (and therefore a fresh
   * announcement) for screen readers.
   */
  const push = useCallback(
    (
      message: string,
      setter: (next: string) => void,
      timerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>
    ) => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      setter("");
      timerRef.current = setTimeout(() => {
        setter(message);
        timerRef.current = null;
      }, 0);
    },
    []
  );

  const announcePolite = useCallback(
    (message: string) => push(message, setPoliteMessage, politeTimerRef),
    [push]
  );

  const announceAssertive = useCallback(
    (message: string) => push(message, setAssertiveMessage, assertiveTimerRef),
    [push]
  );

  const value = useMemo<Announcer>(
    () => ({ announcePolite, announceAssertive }),
    [announcePolite, announceAssertive]
  );

  return (
    <LiveRegionContext.Provider value={value}>
      {children}
      <div
        data-testid="live-region-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        style={SR_ONLY_STYLE}
      >
        {politeMessage}
      </div>
      <div
        data-testid="live-region-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        style={SR_ONLY_STYLE}
      >
        {assertiveMessage}
      </div>
    </LiveRegionContext.Provider>
  );
}

/**
 * Access the announcer. Must be called inside a `<LiveRegionProvider>`.
 *
 * ```tsx
 * const { announcePolite, announceAssertive } = useAnnouncer();
 * announcePolite("Loading elevator summaries");
 * announceAssertive("Failed to load alerts: network error");
 * ```
 */
export function useAnnouncer(): Announcer {
  const ctx = useContext(LiveRegionContext);
  if (ctx === null) {
    throw new Error("useAnnouncer must be used within a LiveRegionProvider");
  }
  return ctx;
}
