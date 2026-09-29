import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface NotFound1Props {
  className?: string;
  cta?: string;
  description?: string;
  href?: string;
  imageSrc?: string;
  title?: string;
  onHome?: () => void;
}

export default function NotFound1({
  title = "You made the Ogre angry!",
  description = "This room doesn't exist. Turn back before it's too late.",
  cta = "Return to Home Page",
  href = "/",
  imageSrc = "https://www.8bitcn.com/_next/image?url=%2Fimages%2F8bit-ogre.png&w=256&q=75&dpl=dpl_B9Q5u7DD6qZpoCz3VRwuR19npVHK",
  className,
  onHome,
}: NotFound1Props) {
  return (
    <div
      className={cn(
        "grid w-full place-content-center gap-5 bg-background px-4 py-16 text-center md:py-24",
        className
      )}
    >
      <div className="font-bold text-6xl tracking-tight sm:text-8xl">404</div>

      {imageSrc && (
        <div className="flex justify-center -mt-10">
          <img
            alt="404"
            className="pixelated"
            height={200}
            src={imageSrc}
            width={200}
            style={{ imageRendering: "pixelated" }}
          />
        </div>
      )}

      <h1 className="font-bold text-2xl tracking-tight sm:text-4xl">{title}</h1>
      <p className="text-muted-foreground text-xs">{description}</p>

      <div className="flex justify-center">
        {onHome ? (
          <Button onClick={onHome}>{cta}</Button>
        ) : (
          <a href={href}>
            <Button>{cta}</Button>
          </a>
        )}
      </div>
    </div>
  );
}
