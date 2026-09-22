// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "WODCraftKit",
    platforms: [.iOS(.v16), .macOS(.v13), .watchOS(.v9)],
    products: [
        .library(name: "WODCraftKit", targets: ["WODCraftKit"])
    ],
    swiftLanguageModes: [.v6],
    targets: [
        .target(
            name: "WODCraftKit",
            resources: [
                .copy("Resources/catalog.json"),
                .copy("Resources/library.json"),
                .copy("Resources/workout.schema.json"),
            ]
        ),
        .testTarget(
            name: "WODCraftKitTests",
            dependencies: ["WODCraftKit"],
            resources: [.copy("Resources/conformance")]
        ),
    ]
)
