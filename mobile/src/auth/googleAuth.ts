import { ResponseType } from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { Platform } from "react-native";

// Required by expo-web-browser when returning from the OAuth redirect.
WebBrowser.maybeCompleteAuthSession();

// Platform-specific client IDs from Google Cloud Console.
// - iOS client uses Bundle ID `host.exp.Exponent` (Expo Go's native bundle)
// - Android client uses package `host.exp.exponent` + Expo Go SHA-1
// - Web client uses `https://auth.expo.io/...` redirect (or localhost)
// expo-auth-session picks the right one based on Platform.OS at runtime.
const IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "";
const ANDROID_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? "";
const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "";

/**
 * Hook that returns a `signIn` function plus reactive state.
 * Call this at the top of a React component:
 *
 *   const { signIn, ready } = useGoogleSignIn();
 *   ...
 *   <Button onPress={signIn} disabled={!ready} />
 */
export function useGoogleSignIn(): {
  signIn: () => Promise<string | null>;
  ready: boolean;
} {
  const [request, , promptAsync] = Google.useAuthRequest({
    iosClientId: IOS_CLIENT_ID || undefined,
    androidClientId: ANDROID_CLIENT_ID || undefined,
    webClientId: WEB_CLIENT_ID || undefined,
    scopes: ["openid", "email", "profile"],
    // Web: force IdToken response type (implicit flow) — the default on web
    // only returns an access_token which isn't useful for identity.
    // Native iOS/Android: omit responseType so expo-auth-session uses the
    // authorization code flow, which Google requires for native apps. The
    // id_token comes back via result.authentication.idToken instead.
    ...(Platform.OS === "web" ? { responseType: ResponseType.IdToken } : {}),
    // Force Google to show the account picker. Without this, Google
    // auto-approves the request if the user already has an active session,
    // redirecting the popup so fast that Chrome's Cross-Origin-Opener-Policy
    // prevents expo-web-browser from detecting the close event. The account
    // picker keeps the popup open long enough for the result to propagate.
    extraParams: {
      prompt: "select_account",
    },
  });

  const signIn = async (): Promise<string | null> => {
    console.log("[googleAuth] signIn called, request ready:", !!request, "platform:", Platform.OS);
    if (!request) return null;
    const result = await promptAsync();
    console.log("[googleAuth] promptAsync result type:", result?.type);
    if (result?.type !== "success") return null;

    // 1. Check if we already have an id_token (web implicit flow)
    const directIdToken =
      (result as any).authentication?.idToken ??
      (result.params as { id_token?: string }).id_token;
    if (directIdToken) {
      console.log("[googleAuth] got id_token directly");
      return directIdToken;
    }

    // 2. Native code flow: exchange the auth code for tokens using PKCE
    const code = (result.params as { code?: string }).code;
    if (!code) {
      console.log("[googleAuth] no id_token and no code — giving up");
      return null;
    }

    console.log("[googleAuth] exchanging auth code for tokens via PKCE");
    const codeVerifier = (request as any).codeVerifier;
    const redirectUri = (request as any).redirectUri;
    const clientId = IOS_CLIENT_ID || WEB_CLIENT_ID;

    console.log("[googleAuth] codeVerifier present:", !!codeVerifier);
    console.log("[googleAuth] redirectUri:", redirectUri);

    try {
      const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          code,
          client_id: clientId,
          code_verifier: codeVerifier ?? "",
          grant_type: "authorization_code",
          redirect_uri: redirectUri ?? "",
        }).toString(),
      });
      const tokenData = await tokenResp.json();
      console.log("[googleAuth] token exchange status:", tokenResp.status);
      console.log("[googleAuth] token exchange has id_token:", !!tokenData.id_token);
      if (tokenData.id_token) {
        return tokenData.id_token;
      }
      console.log("[googleAuth] token exchange response:", JSON.stringify(tokenData).slice(0, 300));
      return null;
    } catch (e) {
      console.log("[googleAuth] token exchange failed:", (e as Error).message);
      return null;
    }
  };

  return { signIn, ready: request !== null };
}
