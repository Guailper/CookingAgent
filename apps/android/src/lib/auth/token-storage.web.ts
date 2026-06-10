const ACCESS_TOKEN_KEY = "cooking-agent.access-token";

export const tokenStorage = {
  get: async () => sessionStorage.getItem(ACCESS_TOKEN_KEY),
  set: async (token: string) => {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  },
  remove: async () => {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  },
};
