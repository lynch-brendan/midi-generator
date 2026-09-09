// macOS-specific helpers for making the audio-engine subprocess behave like a
// floating helper: its windows appear (needed for plugin UIs), but the process
// itself never steals keyboard focus from Nasty (the Electron parent).

#import <Cocoa/Cocoa.h>
#import <objc/runtime.h>
#include <cstdio>
#include <unistd.h>
#include <unordered_map>

namespace nasty {

// Set of NSWindows we want to be non-key (kept as raw pointers — we never
// deref, just membership-test). Touched only on the main thread.
static NSMutableSet* nastyNonKeyWindows = nil;

// Per-class original canBecomeKeyWindow IMPs. JUCE creates a fresh NSWindow
// subclass per plugin window (JUCEWindow_XXXX) and each one overrides
// canBecomeKeyWindow. A plain NSWindow-level IMP swap doesn't reach these
// subclasses — Objective-C dispatch finds the subclass's own method first.
// So we install our override on each dynamic class as we encounter it, and
// remember the original per class so unmarked windows of the same class still
// behave normally.
static std::unordered_map<Class, IMP>* originalCanBecomeKeyByClass = nullptr;

static BOOL nasty_canBecomeKeyWindow(id self, SEL _cmd) {
    if (nastyNonKeyWindows && [nastyNonKeyWindows containsObject:self]) return NO;
    if (originalCanBecomeKeyByClass) {
        Class cls = object_getClass(self);
        auto it = originalCanBecomeKeyByClass->find(cls);
        if (it != originalCanBecomeKeyByClass->end()) {
            return ((BOOL(*)(id, SEL)) it->second)(self, _cmd);
        }
    }
    return YES;
}

static void ensureRegistriesInitialized() {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        nastyNonKeyWindows = [[NSMutableSet alloc] init];
        originalCanBecomeKeyByClass = new std::unordered_map<Class, IMP>();
    });
}

static void installOverrideOnClass(Class cls) {
    if (!cls || !originalCanBecomeKeyByClass) return;
    if (originalCanBecomeKeyByClass->count(cls)) return;
    Method m = class_getInstanceMethod(cls, @selector(canBecomeKeyWindow));
    if (!m) return;
    IMP orig = method_getImplementation(m);
    (*originalCanBecomeKeyByClass)[cls] = orig;
    method_setImplementation(m, (IMP) nasty_canBecomeKeyWindow);
    fprintf(stderr, "[MacHelpers] installed canBecomeKeyWindow override on %s\n",
            class_getName(cls));
}

// Parent app (Electron/Nasty) captured at startup. When the user clicks a
// plugin window and macOS makes the engine app active, we immediately hand
// activation back to Nasty so the DAW keeps receiving keystrokes.
static NSRunningApplication* nastyParentApp = nil;
static id nastyActivationObserver = nil;
static id nastyMouseUpMonitor = nil;

static void reactivateParent() {
    if (nastyParentApp && ![nastyParentApp isTerminated]) {
        [nastyParentApp activateWithOptions:NSApplicationActivateAllWindows];
    }
}

// Install baseline registries and the NSWindow override. Per-subclass
// overrides get installed lazily as plugin windows appear.
void setSubprocessAsAgentApp() {
    if (!NSApp) [NSApplication sharedApplication];
    ensureRegistriesInitialized();
    installOverrideOnClass([NSWindow class]);

    // Capture parent process (Electron) so we can re-activate it if the engine
    // becomes active from a plugin-window click.
    if (!nastyParentApp) {
        pid_t ppid = getppid();
        nastyParentApp = [NSRunningApplication runningApplicationWithProcessIdentifier:ppid];
    }

    // Whenever the engine app becomes active, immediately hand activation
    // back to Nasty. Keeps keyboard focus with the DAW even when the user
    // clicks a plugin window.
    //
    // Exception: if the engine is showing a modal dialog (e.g. an NSOpenPanel
    // that a plugin opened to load a sample), leave it active — the user
    // needs to interact with it. Otherwise we'd yank focus back and the
    // dialog's clicks wouldn't land.
    if (!nastyActivationObserver) {
        nastyActivationObserver = [[NSNotificationCenter defaultCenter]
            addObserverForName:NSApplicationDidBecomeActiveNotification
                        object:nil
                         queue:[NSOperationQueue mainQueue]
                    usingBlock:^(NSNotification*) {
            // Leave engine active when it's showing a modal dialog opened
            // via NSApp modal loop (NSOpenPanel via runModal, etc.) —
            // otherwise the user can't interact with it.
            if ([NSApp modalWindow]) return;

            // If mouse is currently held (dragging a plugin window,
            // resizing, dragging a knob), don't swap mid-drag — it jerks.
            // Wait for mouse-up, then swap.
            if ([NSEvent pressedMouseButtons] != 0) {
                if (nastyMouseUpMonitor) return; // already waiting
                nastyMouseUpMonitor = [NSEvent addLocalMonitorForEventsMatchingMask:NSEventMaskLeftMouseUp
                                                                            handler:^NSEvent*(NSEvent* e) {
                    [NSEvent removeMonitor:nastyMouseUpMonitor];
                    nastyMouseUpMonitor = nil;
                    reactivateParent();
                    return e;
                }];
                return;
            }
            reactivateParent();
        }];
    }
}

void makeWindowNonActivating(void* nativeViewHandle) {
    NSView* view = (__bridge NSView*) nativeViewHandle;
    if (!view) return;
    NSWindow* win = [view window];
    if (!win) return;

    // Float above the DAW window and stay visible while Nasty is focused.
    [win setLevel:NSFloatingWindowLevel];
    [win setHidesOnDeactivate:NO];
    [win setCollectionBehavior:(NSWindowCollectionBehaviorMoveToActiveSpace |
                                NSWindowCollectionBehaviorFullScreenAuxiliary)];

    ensureRegistriesInitialized();

    // Install the canBecomeKeyWindow override on this window's *actual* class.
    // Without this, JUCE's per-window subclass IMP wins and the plugin window
    // still becomes key on click.
    installOverrideOnClass(object_getClass(win));

    // Mark this window so canBecomeKeyWindow returns NO — clicks on it will
    // interact with plugin controls but keyboard focus stays with the DAW.
    [nastyNonKeyWindows addObject:win];
}

// Is the engine subprocess itself the currently active app? True when the
// user is interacting with a plugin dialog we opened, false when they're in
// Nasty (or Chrome, or anywhere else).
bool isEngineAppActive() {
    return NSApp && [NSApp isActive];
}

// Raise/lower a plugin window's level so it floats above Nasty while Nasty
// is the active app, and drops to normal (coverable by other apps) when the
// user Cmd+Tabs away. Called on the message thread.
void setWindowFloating(void* nativeViewHandle, bool floating) {
    NSView* view = (__bridge NSView*) nativeViewHandle;
    if (!view) return;
    NSWindow* win = [view window];
    if (!win) return;
    [win setLevel:(floating ? NSFloatingWindowLevel : NSNormalWindowLevel)];
}

} // namespace nasty
