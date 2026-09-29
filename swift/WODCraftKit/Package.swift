// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "WODCraftKit",
    platforms: [.iOS(.v16), .macOS(.v13), .watchOS(.v9)],
    products: [
        .library(name: "WODCraftKit", targets: ["WODCraftKit"]),
        .executable(name: "wodcraftc", targets: ["wodcraftc"]),
    ],
    targets: [
        .target(
            name: "WODCraftKit",
            resources: [
                .copy("Resources/catalog.json"),
                .copy("Resources/library.json"),
                .copy("Resources/workout.schema.json"),
            ]
        ),
        .executableTarget(name: "wodcraftc", dependencies: ["WODCraftKit"]),
        .testTarget(
            name: "WODCraftKitTests",
            dependencies: ["WODCraftKit"],
            resources: [.copy("Resources/conformance")]
        ),
    ],
    swiftLanguageModes: [.v6]
)
