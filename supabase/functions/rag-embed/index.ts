import "jsr:@supabase/functions-js/edge-runtime.d.ts"

Deno.serve(async (req) => {
  try {
    const body = await req.json()
    const text = typeof body?.text === "string" ? body.text.trim() : ""
    if (!text) return Response.json({ error: "text is required" }, { status: 400 })

    // Supabase Edge Runtime provides this model locally; no external embedding API/key.
    const model = new Supabase.ai.Session("gte-small")
    const embedding = await model.run(text, {
      mean_pool: true,
      normalize: true,
    })

    return Response.json({ embedding })
  } catch (error) {
    console.error(error)
    return Response.json({ error: "embedding generation failed" }, { status: 500 })
  }
})
