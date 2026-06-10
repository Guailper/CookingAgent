import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_KEY = "cooking-agent.access-token";

export const tokenStorage = {
  get: () => SecureStore.getItemAsync(ACCESS_TOKEN_KEY),
  set: (token: string) => SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token),
  remove: () => SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY),
};
