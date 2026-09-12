/**
 * `react-native-web` alias for tamagui's web build (see vite.config.ts): tamagui's own
 * fake-react-native covers Platform/View/ScrollView/…, and the two APIs it lacks are
 * stubbed here. The real react-native-web never enters the bundle; no component this page
 * renders reaches these at runtime except `Linking` (via tamagui's Anchor).
 */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore -- the shim package ships no types
export * from "@tamagui/fake-react-native";

export const Linking = {
  openURL: (url: string): Promise<void> => {
    window.open(url, "_blank", "noopener");
    return Promise.resolve();
  },
  canOpenURL: (): Promise<boolean> => Promise.resolve(true),
};

/** Only tamagui's Spinner (unused on this page) renders it. */
export const ActivityIndicator = (): null => null;

/** Only tamagui's Sheet (unused on this page) touches it. */
export const PanResponder = {
  create: () => ({ panHandlers: {} }),
};
