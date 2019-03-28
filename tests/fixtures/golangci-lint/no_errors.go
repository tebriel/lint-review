package main

import (
	"flag"
	"fmt"
)

func main() {
	flag.Parse()

	fmt.Printf("Hello %s", flag.Arg(0))
}
