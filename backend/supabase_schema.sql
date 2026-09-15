create table if not exists public.scans (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    image_path text not null,
    disease text not null,
    answer text not null,
    sources jsonb not null default '[]'::jsonb,
    language text not null default 'en',
    created_at timestamptz not null default now()
);

create table if not exists public.farmer_profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    phone text not null,
    full_name text not null,
    created_at timestamptz not null default now()
);

alter table public.farmer_profiles add column if not exists full_name text not null default '';
alter table public.scans add column if not exists language text not null default 'en';
create unique index if not exists farmer_profiles_phone_key on public.farmer_profiles (phone);

alter table public.scans enable row level security;
alter table public.farmer_profiles enable row level security;

drop policy if exists "Users can read their own profile" on public.farmer_profiles;
drop policy if exists "Users can read their own scans" on public.scans;
drop policy if exists "Users can create their own scans" on public.scans;

create policy "Users can read their own profile"
    on public.farmer_profiles for select using (auth.uid() = user_id);

create policy "Users can read their own scans"
    on public.scans for select using (auth.uid() = user_id);

create policy "Users can create their own scans"
    on public.scans for insert with check (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('crop-images', 'crop-images', false)
on conflict (id) do nothing;