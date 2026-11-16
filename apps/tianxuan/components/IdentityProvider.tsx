"use client";
import { createContext, useContext, type ReactNode } from "react";

interface Identity { id: string; name: string; email: string; role: string }
const Context = createContext<Identity | null>(null);
export function IdentityProvider({identity, children}: {identity: Identity | null; children: ReactNode}) {
  return <Context.Provider value={identity}>{children}</Context.Provider>;
}
export function useIdentity() { return useContext(Context); }
