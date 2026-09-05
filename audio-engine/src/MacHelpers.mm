// macOS-specific helpers for making the audio-engine subprocess behave like a
// floating helper: its windows appear (needed for plugin UIs), but the process
// itself never steals keyboard focus from Nasty (the Electron parent).

#import <Cocoa/Cocoa.h>
#import <objc/runtime.h>

namespace nasty {

// Set of NSWindows we want to be non-key (kept as raw pointers — we never
// deref, just membership-test). Touched only on the main thread.
static NSMutableSet* nastyNonKeyWindows = nil;
static IMP originalCanBecomeKey = NULL;

static BOOL nasty_canBecomeKeyWindow(id self, SEL /*_cmd*/) {
    if (nastyNonKeyWindows && [nastyNonKeyWindows containsObject:self]) return NO;
    if (originalCanBecomeKey)
        return ((BOOL(*)(id, SEL)) originalCanBecomeKey)(self, @selector(canBecomeKeyWindow));
    return YES;
}

static void installNonKeyOverrideOnce() {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        nastyNonKeyWindows = [[NSMutableSet alloc] init];
        Method m = class_getInstanceMethod([NSWindow class], @selector(canBecomeKeyWindow));
        if (m) {
            originalCanBecomeKey = method_getImplementation(m);
            method_setImplementation(m, (IMP) nasty_canBecomeKeyWindow);
        }
    });
}

// Install the canBecomeKeyWindow override for plugin windows we mark.
// (We used to also set NSApplicationActivationPolicyAccessory here, but that
// broke audio output on some plugin instances, so we stopped.)
void setSubprocessAsAgentApp() {
    if (!NSApp) [NSApplication sharedApplication];
    installNonKeyOverrideOnce();
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

    // Mark this window so canBecomeKeyWindow returns NO — clicks on it will
    // interact with plugin controls but keyboard focus stays with the DAW.
    if (nastyNonKeyWindows) [nastyNonKeyWindows addObject:win];
}

} // namespace nasty
