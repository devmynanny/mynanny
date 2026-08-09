"use client";
import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { NannyCard, NannyResult } from "@/app/caregivers/page";
import { Heart, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

export default function Favorites(){
  const [nannies,setNannies]=useState<NannyResult[]>([]); const [loading,setLoading]=useState(true);
  useEffect(()=>{apiJson<{results:NannyResult[]}>("/parents/me/favorites/details").then((data)=>setNannies(data.results||[])).finally(()=>setLoading(false));},[]);
  async function remove(id:number){await apiJson(`/parents/me/favorites/${id}`,{method:"DELETE"});setNannies((current)=>current.filter((n)=>n.nanny_id!==id));}
  return <AuthenticatedPage>{()=> <div className="mx-auto max-w-6xl"><div className="eyebrow">Your shortlist</div><h1 className="display mt-2 text-4xl sm:text-5xl">Favourite nannies.</h1>{loading?<div className="mt-12 flex justify-center text-[var(--muted)]"><LoaderCircle className="animate-spin"/></div>:nannies.length?<div className="mt-7 grid gap-5 lg:grid-cols-3">{nannies.map((nanny)=><NannyCard key={nanny.nanny_id} nanny={nanny} favourite onFavourite={()=>remove(nanny.nanny_id)}/>)}</div>:<div className="card mt-7 p-10 text-center"><Heart className="mx-auto text-[var(--coral)]"/><h2 className="mt-4 text-xl font-bold">Your shortlist is ready when you are</h2><p className="mt-2 text-[var(--muted)]">Tap the heart on any nanny profile to save them here.</p></div>}</div>}</AuthenticatedPage>;
}
