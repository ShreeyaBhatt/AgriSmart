import Card from "./Card.jsx";

const Box = ({ className }) => <div className={"animate-pulse rounded-lg bg-line " + className} />;

export function ProfileSkeleton() {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <Box className="h-6 w-40" />
        <Box className="h-5 w-24 rounded-full" />
      </div>
      <Box className="mt-4 h-9 w-full" />
      <Box className="mt-4 h-20 w-full" />
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Box key={i} className="h-16" />
        ))}
      </div>
    </Card>
  );
}

export function PanelsSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {[0, 1].map((c) => (
        <Card key={c} className="p-5">
          <Box className="h-4 w-32" />
          <div className="mt-3 space-y-2">
            {[0, 1, 2].map((i) => (
              <Box key={i} className="h-16" />
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}
