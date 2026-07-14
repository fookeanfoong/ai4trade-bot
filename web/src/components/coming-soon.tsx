import { Link } from '@/i18n/routing';
import { Construction } from 'lucide-react';

export function ComingSoon({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="container flex min-h-[50vh] flex-col items-center justify-center py-20 text-center">
      <Construction className="h-10 w-10 text-primary" />
      <h1 className="mt-4 text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{phase}</p>
      <Link
        href="/providers"
        className="mt-6 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        浏览全部中转站
      </Link>
    </div>
  );
}
