import AsyncStorage from '@react-native-async-storage/async-storage';
import * as LocalAuthentication from 'expo-local-authentication';
import { AppStateStatus } from 'react-native';
import { create } from 'zustand';
import { authAPI, authTokenStore, setUnauthorizedHandler } from './api';

const FACE_UNLOCK_STORAGE_KEY = 'fasttrade_face_unlock_enabled';

export type AuthUser = {
  username?: string;
  auth_enabled?: boolean;
  token_exp?: number;
};

type AuthState = {
  bootstrapped: boolean;
  isAuthenticated: boolean;
  isLocked: boolean;
  biometricEnabled: boolean;
  biometricAvailable: boolean;
  user: AuthUser | null;
  bootstrap: () => Promise<void>;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setBiometricEnabled: (enabled: boolean) => Promise<{ ok: boolean; reason?: string }>;
  unlockWithBiometrics: () => Promise<{ success: boolean; error: string | null }>;
  lockIfNeeded: () => void;
  handleAppStateChange: (nextState: AppStateStatus) => void;
};

let previousAppState: AppStateStatus = 'active';

async function detectBiometricAvailability() {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  const isEnrolled = hasHardware ? await LocalAuthentication.isEnrolledAsync() : false;
  return hasHardware && isEnrolled;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  bootstrapped: false,
  isAuthenticated: false,
  isLocked: false,
  biometricEnabled: false,
  biometricAvailable: false,
  user: null,

  bootstrap: async () => {
    const [token, biometricPref, biometricAvailable] = await Promise.all([
      authTokenStore.get(),
      AsyncStorage.getItem(FACE_UNLOCK_STORAGE_KEY),
      detectBiometricAvailability(),
    ]);

    const biometricEnabled = biometricPref === 'true' && biometricAvailable;

    if (!token) {
      set({
        bootstrapped: true,
        isAuthenticated: false,
        isLocked: false,
        biometricEnabled,
        biometricAvailable,
        user: null,
      });
      return;
    }

    try {
      const response = await authAPI.me();
      set({
        bootstrapped: true,
        isAuthenticated: true,
        isLocked: biometricEnabled,
        biometricEnabled,
        biometricAvailable,
        user: response.data || null,
      });
    } catch {
      await authTokenStore.clear();
      set({
        bootstrapped: true,
        isAuthenticated: false,
        isLocked: false,
        biometricEnabled,
        biometricAvailable,
        user: null,
      });
    }
  },

  signIn: async (username: string, password: string) => {
    const response = await authAPI.login(username, password);
    const accessToken = response.data?.access_token;
    if (!accessToken) {
      throw new Error('Missing access token');
    }

    await authTokenStore.set(accessToken);
    const me = await authAPI.me();
    const state = get();
    set({
      isAuthenticated: true,
      isLocked: false,
      user: me.data || null,
      biometricEnabled: state.biometricEnabled,
      biometricAvailable: state.biometricAvailable,
      bootstrapped: true,
    });
  },

  signOut: async () => {
    await authTokenStore.clear();
    set({
      isAuthenticated: false,
      isLocked: false,
      user: null,
    });
  },

  refreshUser: async () => {
    const response = await authAPI.me();
    set({ user: response.data || null });
  },

  setBiometricEnabled: async (enabled: boolean) => {
    const available = await detectBiometricAvailability();
    if (enabled && !available) {
      set({ biometricAvailable: false, biometricEnabled: false });
      await AsyncStorage.setItem(FACE_UNLOCK_STORAGE_KEY, 'false');
      return { ok: false, reason: 'Biometric authentication is not available or not enrolled on this device.' };
    }

    await AsyncStorage.setItem(FACE_UNLOCK_STORAGE_KEY, enabled ? 'true' : 'false');
    set((state) => ({
      biometricAvailable: available,
      biometricEnabled: enabled && available,
      isLocked: enabled ? state.isLocked : false,
    }));
    return { ok: true };
  },

  unlockWithBiometrics: async () => {
    const state = get();
    if (!state.biometricEnabled) {
      set({ isLocked: false });
      return { success: true, error: null };
    }

    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Unlock FastTrade',
      cancelLabel: 'Cancel',
      // Keep device passcode as an iOS fallback — Face ID is tried first, passcode
      // is shown automatically by iOS if biometrics fail or are locked out.
      disableDeviceFallback: false,
    });

    if (result.success) {
      set({ isLocked: false });
      return { success: true, error: null };
    }

    const errorCode = (result as any).error ?? 'unknown';

    // If biometrics are not enrolled at all, auto-disable the feature so the
    // user isn't stuck on the lock screen forever.
    if (errorCode === 'not_enrolled') {
      await AsyncStorage.setItem(FACE_UNLOCK_STORAGE_KEY, 'false');
      set({ biometricEnabled: false, isLocked: false });
      return { success: true, error: null };
    }

    return { success: false, error: errorCode as string };
  },

  lockIfNeeded: () => {
    const state = get();
    if (state.isAuthenticated && state.biometricEnabled) {
      set({ isLocked: true });
    }
  },

  handleAppStateChange: (nextState: AppStateStatus) => {
    if (previousAppState === 'active' && nextState.match(/inactive|background/)) {
      get().lockIfNeeded();
    }
    previousAppState = nextState;
  },
}));

setUnauthorizedHandler(async () => {
  const state = useAuthStore.getState();
  if (state.isAuthenticated) {
    await state.signOut();
  }
});
